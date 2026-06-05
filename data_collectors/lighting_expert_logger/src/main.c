#include "csv_logger.h"
#include "dataset_commands.h"
#include "uart_line_parser.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <zephyr/device.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/printk.h>

LOG_MODULE_REGISTER(lighting_expert_logger, LOG_LEVEL_INF);

#define ROBOT_ID "porter_dev"
#define EXPERT_NAME "lighting_expert"
#define FAULT_SUBSYSTEM "lighting"
#define LOG_PERIOD_MS 100
#define TELEMETRY_STALE_MS 500
#define UART_BUF_LEN 128
#define LINE_BUF_LEN 384

struct lighting_telemetry {
	struct k_mutex lock;
	int brightness_command;
	double light_current_a;
	double light_voltage_v;
	double light_sensor_lux;
	double light_driver_temp_c;
	int64_t last_rx_ms;
};

static struct lighting_telemetry telemetry;
static char uart_buffer[UART_BUF_LEN];
static struct uart_line_parser parser;

#if DT_NODE_HAS_STATUS(DT_ALIAS(lighting_tel_uart), okay)
static const struct device *const telemetry_uart = DEVICE_DT_GET(DT_ALIAS(lighting_tel_uart));
#else
static const struct device *const telemetry_uart;
#endif

#if DT_NODE_HAS_PROP(DT_ALIAS(light_fault_gpio), gpios)
static const struct gpio_dt_spec light_fault_gpio =
	GPIO_DT_SPEC_GET(DT_ALIAS(light_fault_gpio), gpios);
#else
static const struct gpio_dt_spec light_fault_gpio = { 0 };
#endif

static const struct dataset_config dataset_config = {
	.expert_name = EXPERT_NAME,
	.fault_subsystem = FAULT_SUBSYSTEM,
	.robot_id = ROBOT_ID,
	.raw_header = DATASET_COMMON_COLUMNS
		      ",brightness_command,light_current_a,light_voltage_v,light_sensor_lux,"
		      "light_driver_temp_c,light_fault_gpio,telemetry_valid,telemetry_age_ms\n",
	.metadata_extra = "sample_period_ms=100\ntelemetry_stale_ms=500\n",
};

static int optional_gpio_read(const struct gpio_dt_spec *spec)
{
	int ret;

	if (spec == NULL || spec->port == NULL || !device_is_ready(spec->port)) {
		return -1;
	}

	ret = gpio_pin_get_dt(spec);
	return ret < 0 ? -1 : ret;
}

static void optional_gpio_configure(const struct gpio_dt_spec *spec, const char *name)
{
	int ret;

	if (spec == NULL || spec->port == NULL) {
		LOG_WRN("%s not configured", name);
		return;
	}
	if (!device_is_ready(spec->port)) {
		LOG_WRN("%s GPIO port not ready", name);
		return;
	}

	ret = gpio_pin_configure_dt(spec, GPIO_INPUT);
	if (ret != 0) {
		LOG_WRN("%s configure failed: %d", name, ret);
	}
}

static int parse_int_token(char **saveptr, int *value)
{
	char *token = strtok_r(NULL, ",", saveptr);
	char *end;
	long parsed;

	if (token == NULL) {
		return -EINVAL;
	}
	parsed = strtol(token, &end, 10);
	if (*end != '\0') {
		return -EINVAL;
	}
	*value = (int)parsed;
	return 0;
}

static int parse_double_token(char **saveptr, double *value)
{
	char *token = strtok_r(NULL, ",", saveptr);
	char *end;
	double parsed;

	if (token == NULL) {
		return -EINVAL;
	}
	parsed = strtod(token, &end);
	if (*end != '\0') {
		return -EINVAL;
	}
	*value = parsed;
	return 0;
}

static void handle_telemetry_line(const char *line, void *user_data)
{
	char local[UART_BUF_LEN];
	char *saveptr;
	char *prefix;
	struct lighting_telemetry next;

	ARG_UNUSED(user_data);

	strncpy(local, line, sizeof(local) - 1);
	local[sizeof(local) - 1] = '\0';

	prefix = strtok_r(local, ",", &saveptr);
	if (prefix == NULL || strcmp(prefix, "LGT") != 0) {
		return;
	}

	if (parse_int_token(&saveptr, &next.brightness_command) != 0 ||
	    parse_double_token(&saveptr, &next.light_current_a) != 0 ||
	    parse_double_token(&saveptr, &next.light_voltage_v) != 0 ||
	    parse_double_token(&saveptr, &next.light_sensor_lux) != 0 ||
	    parse_double_token(&saveptr, &next.light_driver_temp_c) != 0) {
		LOG_WRN("Invalid LGT line");
		return;
	}

	next.last_rx_ms = k_uptime_get();
	k_mutex_lock(&telemetry.lock, K_FOREVER);
	telemetry = next;
	k_mutex_unlock(&telemetry.lock);
}

static void logger_thread(void)
{
	char line[LINE_BUF_LEN];
	struct dataset_snapshot snapshot;
	struct lighting_telemetry sample;
	int64_t now;
	int age_ms;
	bool valid;
	int offset;

	while (true) {
		if (telemetry_uart != NULL) {
			uart_line_parser_poll(&parser);
		}

		k_sleep(K_MSEC(LOG_PERIOD_MS));

		if (!dataset_is_run_active()) {
			continue;
		}

		now = k_uptime_get();
		dataset_get_snapshot(&snapshot);

		k_mutex_lock(&telemetry.lock, K_FOREVER);
		sample = telemetry;
		k_mutex_unlock(&telemetry.lock);

		age_ms = sample.last_rx_ms > 0 ? (int)(now - sample.last_rx_ms) : -1;
		valid = age_ms >= 0 && age_ms <= TELEMETRY_STALE_MS;

		offset = dataset_write_common_prefix(line, sizeof(line), &snapshot, now);
		if (offset < 0 || offset >= (int)sizeof(line)) {
			continue;
		}

		csv_append_int(line, sizeof(line), &offset, valid ? sample.brightness_command : -1);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.light_current_a : -1.0);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.light_voltage_v : -1.0);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.light_sensor_lux : -1.0);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.light_driver_temp_c : -1.0);
		csv_append_int(line, sizeof(line), &offset, optional_gpio_read(&light_fault_gpio));
		csv_append_bool(line, sizeof(line), &offset, valid);
		csv_append_int(line, sizeof(line), &offset, age_ms);
		snprintf(line + offset, sizeof(line) - offset, "\n");

		dataset_write_raw_line(line);
	}
}

K_THREAD_DEFINE(logger_tid, 4096, logger_thread, NULL, NULL, NULL, 5, 0, K_FOREVER);

int main(void)
{
	int ret;

	k_mutex_init(&telemetry.lock);

	printk("========================================\n");
	printk("Lighting Expert Logger\n");
	printk("========================================\n");
	printk("UART format: LGT,brightness_command,light_current,light_voltage,light_sensor_lux,light_driver_temp\n");

	optional_gpio_configure(&light_fault_gpio, "light-fault-gpio");

	ret = dataset_init(&dataset_config);
	if (ret != 0) {
		LOG_ERR("SD storage is not ready: %d", ret);
	}

	if (telemetry_uart != NULL && device_is_ready(telemetry_uart)) {
		uart_line_parser_init(&parser, telemetry_uart, uart_buffer, sizeof(uart_buffer),
				      handle_telemetry_line, NULL);
		LOG_INF("Lighting telemetry UART ready");
	} else {
		LOG_WRN("No lighting-tel-uart alias is enabled; UART telemetry will remain invalid");
	}

	k_thread_start(logger_tid);
	return 0;
}
