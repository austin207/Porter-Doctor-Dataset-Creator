#include "csv_logger.h"
#include "dataset_commands.h"
#include "uart_line_parser.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <zephyr/device.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/printk.h>

LOG_MODULE_REGISTER(motor_expert_logger, LOG_LEVEL_INF);

#define ROBOT_ID "porter_dev"
#define EXPERT_NAME "motor_expert"
#define FAULT_SUBSYSTEM "motor"
#define LOG_PERIOD_MS 100
#define TELEMETRY_STALE_MS 500
#define UART_BUF_LEN 128
#define LINE_BUF_LEN 384

struct motor_telemetry {
	struct k_mutex lock;
	int pwm_left;
	int pwm_right;
	int rpm_left;
	int rpm_right;
	long long encoder_left;
	long long encoder_right;
	double current_left_a;
	double current_right_a;
	int64_t last_rx_ms;
};

static struct motor_telemetry telemetry;
static char uart_buffer[UART_BUF_LEN];
static struct uart_line_parser parser;

#if DT_NODE_HAS_STATUS(DT_ALIAS(motor_tel_uart), okay)
static const struct device *const telemetry_uart = DEVICE_DT_GET(DT_ALIAS(motor_tel_uart));
#else
static const struct device *const telemetry_uart;
#endif

static const struct dataset_config dataset_config = {
	.expert_name = EXPERT_NAME,
	.fault_subsystem = FAULT_SUBSYSTEM,
	.robot_id = ROBOT_ID,
	.raw_header = DATASET_COMMON_COLUMNS
		      ",pwm_left,pwm_right,rpm_left,rpm_right,encoder_count_left,"
		      "encoder_count_right,current_left_a,current_right_a,vibration_rms,"
		      "vibration_peak,motor_temp_left_c,motor_temp_right_c,telemetry_valid,"
		      "telemetry_age_ms\n",
	.metadata_extra = "sample_period_ms=100\ntelemetry_stale_ms=500\n",
};

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

static int parse_i64_token(char **saveptr, long long *value)
{
	char *token = strtok_r(NULL, ",", saveptr);
	char *end;
	long long parsed;

	if (token == NULL) {
		return -EINVAL;
	}

	parsed = strtoll(token, &end, 10);
	if (*end != '\0') {
		return -EINVAL;
	}

	*value = parsed;
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
	struct motor_telemetry next;

	ARG_UNUSED(user_data);

	strncpy(local, line, sizeof(local) - 1);
	local[sizeof(local) - 1] = '\0';

	prefix = strtok_r(local, ",", &saveptr);
	if (prefix == NULL || strcmp(prefix, "TEL") != 0) {
		return;
	}

	if (parse_int_token(&saveptr, &next.pwm_left) != 0 ||
	    parse_int_token(&saveptr, &next.pwm_right) != 0 ||
	    parse_int_token(&saveptr, &next.rpm_left) != 0 ||
	    parse_int_token(&saveptr, &next.rpm_right) != 0 ||
	    parse_i64_token(&saveptr, &next.encoder_left) != 0 ||
	    parse_i64_token(&saveptr, &next.encoder_right) != 0 ||
	    parse_double_token(&saveptr, &next.current_left_a) != 0 ||
	    parse_double_token(&saveptr, &next.current_right_a) != 0) {
		LOG_WRN("Invalid TEL line");
		return;
	}

	next.last_rx_ms = k_uptime_get();
	k_mutex_lock(&telemetry.lock, K_FOREVER);
	telemetry.pwm_left = next.pwm_left;
	telemetry.pwm_right = next.pwm_right;
	telemetry.rpm_left = next.rpm_left;
	telemetry.rpm_right = next.rpm_right;
	telemetry.encoder_left = next.encoder_left;
	telemetry.encoder_right = next.encoder_right;
	telemetry.current_left_a = next.current_left_a;
	telemetry.current_right_a = next.current_right_a;
	telemetry.last_rx_ms = next.last_rx_ms;
	k_mutex_unlock(&telemetry.lock);
}

static void logger_thread(void)
{
	char line[LINE_BUF_LEN];
	struct dataset_snapshot snapshot;
	struct motor_telemetry sample;
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

		csv_append_int(line, sizeof(line), &offset, valid ? sample.pwm_left : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.pwm_right : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.rpm_left : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.rpm_right : -1);
		csv_append_i64(line, sizeof(line), &offset, valid ? sample.encoder_left : -1);
		csv_append_i64(line, sizeof(line), &offset, valid ? sample.encoder_right : -1);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.current_left_a : -1.0);
		csv_append_double(line, sizeof(line), &offset, valid ? sample.current_right_a : -1.0);
		csv_append_double(line, sizeof(line), &offset, -1.0);
		csv_append_double(line, sizeof(line), &offset, -1.0);
		csv_append_double(line, sizeof(line), &offset, -1.0);
		csv_append_double(line, sizeof(line), &offset, -1.0);
		csv_append_bool(line, sizeof(line), &offset, valid);
		csv_append_int(line, sizeof(line), &offset, age_ms);
		snprintf(line + offset, sizeof(line) - offset, "\n");

		dataset_write_raw_line(line);
	}
}

K_THREAD_DEFINE(logger_tid, 4096, logger_thread, NULL, NULL, NULL, 5, 0, 0);

int main(void)
{
	int ret;

	k_mutex_init(&telemetry.lock);

	printk("========================================\n");
	printk("Motor Expert Logger\n");
	printk("========================================\n");
	printk("UART format: TEL,pwm_left,pwm_right,rpm_left,rpm_right,encoder_left,encoder_right,current_left,current_right\n");

	ret = dataset_init(&dataset_config);
	if (ret != 0) {
		LOG_ERR("SD storage is not ready: %d", ret);
	}

	if (telemetry_uart != NULL && device_is_ready(telemetry_uart)) {
		uart_line_parser_init(&parser, telemetry_uart, uart_buffer, sizeof(uart_buffer),
				      handle_telemetry_line, NULL);
		LOG_INF("Motor telemetry UART ready");
	} else {
		LOG_WRN("No motor-tel-uart alias is enabled; telemetry will remain invalid");
	}

	return 0;
}
