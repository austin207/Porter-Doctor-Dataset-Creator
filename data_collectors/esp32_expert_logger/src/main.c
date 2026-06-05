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

LOG_MODULE_REGISTER(esp32_expert_logger, LOG_LEVEL_INF);

#define ROBOT_ID "porter_dev"
#define EXPERT_NAME "esp32_expert"
#define FAULT_SUBSYSTEM "esp32_controller"
#define LOG_PERIOD_MS 100
#define TELEMETRY_STALE_MS 500
#define UART_BUF_LEN 128
#define LINE_BUF_LEN 384
#define RESET_REASON_LEN 32

struct esp32_health {
	struct k_mutex lock;
	int heartbeat_counter;
	int heartbeat_interval_ms;
	char reset_reason[RESET_REASON_LEN];
	int watchdog_count;
	int packet_error_count;
	int task_loop_time_ms;
	int control_loop_jitter_ms;
	int64_t last_rx_ms;
};

static struct esp32_health telemetry;
static char uart_buffer[UART_BUF_LEN];
static struct uart_line_parser parser;

#if DT_NODE_HAS_STATUS(DT_ALIAS(esp32_health_uart), okay)
static const struct device *const telemetry_uart = DEVICE_DT_GET(DT_ALIAS(esp32_health_uart));
#else
static const struct device *const telemetry_uart;
#endif

static const struct dataset_config dataset_config = {
	.expert_name = EXPERT_NAME,
	.fault_subsystem = FAULT_SUBSYSTEM,
	.robot_id = ROBOT_ID,
	.raw_header = DATASET_COMMON_COLUMNS
		      ",heartbeat_counter,heartbeat_interval_ms,reset_reason,watchdog_count,"
		      "packet_error_count,task_loop_time_ms,control_loop_jitter_ms,uart_rx_errors,"
		      "telemetry_valid,telemetry_age_ms\n",
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

static int parse_string_token(char **saveptr, char *value, size_t value_len)
{
	char *token = strtok_r(NULL, ",", saveptr);

	if (token == NULL || value_len == 0) {
		return -EINVAL;
	}

	for (size_t i = 0; token[i] != '\0'; i++) {
		char c = token[i];

		if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
		      (c >= '0' && c <= '9') || c == '_' || c == '-')) {
			return -EINVAL;
		}
	}

	strncpy(value, token, value_len - 1);
	value[value_len - 1] = '\0';
	return 0;
}

static void handle_telemetry_line(const char *line, void *user_data)
{
	char local[UART_BUF_LEN];
	char *saveptr;
	char *prefix;
	struct esp32_health next;
	int64_t now = k_uptime_get();
	int64_t previous_rx;

	ARG_UNUSED(user_data);

	strncpy(local, line, sizeof(local) - 1);
	local[sizeof(local) - 1] = '\0';

	prefix = strtok_r(local, ",", &saveptr);
	if (prefix == NULL || strcmp(prefix, "ESP") != 0) {
		return;
	}

	if (parse_int_token(&saveptr, &next.heartbeat_counter) != 0 ||
	    parse_string_token(&saveptr, next.reset_reason, sizeof(next.reset_reason)) != 0 ||
	    parse_int_token(&saveptr, &next.watchdog_count) != 0 ||
	    parse_int_token(&saveptr, &next.packet_error_count) != 0 ||
	    parse_int_token(&saveptr, &next.task_loop_time_ms) != 0 ||
	    parse_int_token(&saveptr, &next.control_loop_jitter_ms) != 0) {
		LOG_WRN("Invalid ESP line");
		return;
	}

	k_mutex_lock(&telemetry.lock, K_FOREVER);
	previous_rx = telemetry.last_rx_ms;
	next.heartbeat_interval_ms = previous_rx > 0 ? (int)(now - previous_rx) : -1;
	next.last_rx_ms = now;
	telemetry = next;
	k_mutex_unlock(&telemetry.lock);
}

static void logger_thread(void)
{
	char line[LINE_BUF_LEN];
	struct dataset_snapshot snapshot;
	struct esp32_health sample;
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

		csv_append_int(line, sizeof(line), &offset, valid ? sample.heartbeat_counter : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.heartbeat_interval_ms : -1);
		offset += snprintf(line + offset, sizeof(line) - offset, ",%s",
				   valid ? sample.reset_reason : "invalid");
		csv_append_int(line, sizeof(line), &offset, valid ? sample.watchdog_count : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.packet_error_count : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.task_loop_time_ms : -1);
		csv_append_int(line, sizeof(line), &offset, valid ? sample.control_loop_jitter_ms : -1);
		csv_append_int(line, sizeof(line), &offset, (int)uart_line_parser_errors(&parser));
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
	strncpy(telemetry.reset_reason, "unknown", sizeof(telemetry.reset_reason) - 1);

	printk("========================================\n");
	printk("ESP32 Expert Logger\n");
	printk("========================================\n");
	printk("UART format: ESP,heartbeat_counter,reset_reason,watchdog_count,packet_error_count,task_loop_time_ms,control_loop_jitter_ms\n");

	ret = dataset_init(&dataset_config);
	if (ret != 0) {
		LOG_ERR("SD storage is not ready: %d", ret);
	}

	if (telemetry_uart != NULL && device_is_ready(telemetry_uart)) {
		uart_line_parser_init(&parser, telemetry_uart, uart_buffer, sizeof(uart_buffer),
				      handle_telemetry_line, NULL);
		LOG_INF("ESP32 health UART ready");
	} else {
		LOG_WRN("No esp32-health-uart alias is enabled; telemetry will remain invalid");
	}

	k_thread_start(logger_tid);
	return 0;
}
