#include <zephyr/device.h>
#include <zephyr/drivers/sensor.h>
#include <zephyr/fs/fs.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>
#include <zephyr/sys/printk.h>
#include <ff.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

LOG_MODULE_REGISTER(power_expert_logger, LOG_LEVEL_INF);

#define EXPERT_NAME "power_expert"
#define FAULT_SUBSYSTEM "power"
#define ROBOT_ID "porter_dev"
#define LOG_PERIOD_MS 100
#define MAX_LABEL_LEN 32
#define MAX_RUN_ID_LEN 48
#define MAX_PATH_LEN 160

#if !DT_NODE_HAS_STATUS(DT_ALIAS(power_sensor), okay)
#error "Devicetree alias 'power-sensor' must point to an enabled INA226 node"
#endif

static const struct device *const power_sensor = DEVICE_DT_GET(DT_ALIAS(power_sensor));

static FATFS fat_fs;
static struct fs_mount_t sd_mount = {
	.type = FS_FATFS,
	.fs_data = &fat_fs,
	.mnt_point = "/SD:",
};

struct logger_state {
	struct k_mutex lock;
	bool sd_ready;
	bool run_active;
	bool fault_active;
	int severity;
	int64_t run_start_ms;
	char run_id[MAX_RUN_ID_LEN];
	char fault_label[MAX_LABEL_LEN];
	char raw_path[MAX_PATH_LEN];
	char events_path[MAX_PATH_LEN];
	struct fs_file_t raw_file;
	struct fs_file_t events_file;
};

static struct logger_state state;

static double sensor_value_to_d(const struct sensor_value *value)
{
	return (double)value->val1 + ((double)value->val2 / 1000000.0);
}

static void make_safe_token(char *dst, size_t dst_len, const char *src)
{
	size_t out = 0;

	for (size_t i = 0; src[i] != '\0' && out + 1 < dst_len; i++) {
		const char c = src[i];

		if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
		    (c >= '0' && c <= '9') || c == '_' || c == '-') {
			dst[out++] = c;
		} else {
			dst[out++] = '_';
		}
	}

	dst[out] = '\0';
}

static int ensure_dir(const char *path)
{
	int ret = fs_mkdir(path);

	if (ret == 0 || ret == -EEXIST) {
		return 0;
	}

	LOG_ERR("fs_mkdir(%s) failed: %d", path, ret);
	return ret;
}

static int ensure_dataset_dirs(void)
{
	int ret;

	ret = ensure_dir("/SD:/datasets");
	if (ret != 0) {
		return ret;
	}
	ret = ensure_dir("/SD:/datasets/power_expert");
	if (ret != 0) {
		return ret;
	}
	ret = ensure_dir("/SD:/datasets/power_expert/raw");
	if (ret != 0) {
		return ret;
	}
	ret = ensure_dir("/SD:/datasets/power_expert/events");
	if (ret != 0) {
		return ret;
	}
	ret = ensure_dir("/SD:/datasets/power_expert/metadata");
	if (ret != 0) {
		return ret;
	}

	return ensure_dir("/SD:/datasets/power_expert/features");
}

static int write_text(struct fs_file_t *file, const char *text)
{
	const size_t len = strlen(text);
	ssize_t written = fs_write(file, text, len);

	return written == len ? 0 : (written < 0 ? (int)written : -EIO);
}

static int write_event_locked(const char *event_name)
{
	char line[128];
	int64_t now = k_uptime_get();
	double elapsed_s = 0.0;

	if (state.run_start_ms > 0) {
		elapsed_s = (double)(now - state.run_start_ms) / 1000.0;
	}

	snprintf(line, sizeof(line), "%" PRId64 ",%.3f,%s,%d,%s,%d\n",
		 now, elapsed_s, event_name, state.fault_active ? 1 : 0,
		 state.fault_label, state.severity);

	return write_text(&state.events_file, line);
}

static int write_metadata_file(const char *run_id, const char *fault_label, int severity)
{
	struct fs_file_t metadata_file;
	char metadata_path[MAX_PATH_LEN];
	char body[512];
	int ret;

	snprintf(metadata_path, sizeof(metadata_path),
		 "/SD:/datasets/power_expert/metadata/%s.txt", run_id);

	fs_file_t_init(&metadata_file);
	ret = fs_open(&metadata_file, metadata_path, FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	if (ret != 0) {
		return ret;
	}

	snprintf(body, sizeof(body),
		 "run_id=%s\n"
		 "robot_id=%s\n"
		 "expert_name=%s\n"
		 "fault_label=%s\n"
		 "fault_subsystem=%s\n"
		 "severity=%d\n"
		 "sample_period_ms=%d\n",
		 run_id, ROBOT_ID, EXPERT_NAME, fault_label, FAULT_SUBSYSTEM,
		 severity, LOG_PERIOD_MS);

	ret = write_text(&metadata_file, body);
	fs_close(&metadata_file);
	return ret;
}

static int mount_sd_card(void)
{
	int ret = fs_mount(&sd_mount);

	if (ret != 0) {
		LOG_ERR("SD mount failed at %s: %d", sd_mount.mnt_point, ret);
		return ret;
	}

	ret = ensure_dataset_dirs();
	if (ret != 0) {
		return ret;
	}

	state.sd_ready = true;
	LOG_INF("SD card mounted at %s", sd_mount.mnt_point);
	return 0;
}

static int read_power_sample(double *voltage_v, double *current_a, double *power_w)
{
	struct sensor_value voltage;
	struct sensor_value current;
	struct sensor_value power;
	int ret;

	ret = sensor_sample_fetch(power_sensor);
	if (ret != 0) {
		return ret;
	}

	ret = sensor_channel_get(power_sensor, SENSOR_CHAN_VOLTAGE, &voltage);
	if (ret != 0) {
		return ret;
	}

	ret = sensor_channel_get(power_sensor, SENSOR_CHAN_CURRENT, &current);
	if (ret != 0) {
		return ret;
	}

	ret = sensor_channel_get(power_sensor, SENSOR_CHAN_POWER, &power);
	if (ret == 0) {
		*power_w = sensor_value_to_d(&power);
	} else {
		*power_w = sensor_value_to_d(&voltage) * sensor_value_to_d(&current);
	}

	*voltage_v = sensor_value_to_d(&voltage);
	*current_a = sensor_value_to_d(&current);
	return 0;
}

static int cmd_start(const struct shell *shell, size_t argc, char **argv)
{
	char safe_run_id[MAX_RUN_ID_LEN];
	char safe_fault_label[MAX_LABEL_LEN];
	char header[] =
		"timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active,"
		"fault_label,fault_subsystem,severity,battery_voltage_v,"
		"battery_current_a,battery_power_w\n";
	char event_header[] = "timestamp_ms,elapsed_s,event,fault_active,fault_label,severity\n";
	int severity;
	int ret;

	if (argc != 4) {
		shell_error(shell, "usage: start <run_id> <fault_label> <severity>");
		return -EINVAL;
	}

	severity = atoi(argv[3]);
	if (severity < 0 || severity > 5) {
		shell_error(shell, "severity must be 0..5");
		return -EINVAL;
	}

	make_safe_token(safe_run_id, sizeof(safe_run_id), argv[1]);
	make_safe_token(safe_fault_label, sizeof(safe_fault_label), argv[2]);
	if (safe_run_id[0] == '\0' || safe_fault_label[0] == '\0') {
		shell_error(shell, "run_id and fault_label must not be empty");
		return -EINVAL;
	}

	k_mutex_lock(&state.lock, K_FOREVER);

	if (!state.sd_ready) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "SD card is not mounted");
		return -ENODEV;
	}

	if (state.run_active) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "run already active: %s", state.run_id);
		return -EBUSY;
	}

	strncpy(state.run_id, safe_run_id, sizeof(state.run_id) - 1);
	strncpy(state.fault_label, safe_fault_label, sizeof(state.fault_label) - 1);
	state.run_id[sizeof(state.run_id) - 1] = '\0';
	state.fault_label[sizeof(state.fault_label) - 1] = '\0';
	state.severity = severity;
	state.fault_active = false;
	state.run_start_ms = k_uptime_get();

	snprintf(state.raw_path, sizeof(state.raw_path),
		 "/SD:/datasets/power_expert/raw/%s.csv", state.run_id);
	snprintf(state.events_path, sizeof(state.events_path),
		 "/SD:/datasets/power_expert/events/%s_events.csv", state.run_id);

	fs_file_t_init(&state.raw_file);
	fs_file_t_init(&state.events_file);

	ret = fs_open(&state.raw_file, state.raw_path, FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	if (ret != 0) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "failed to open raw file: %d", ret);
		return ret;
	}

	ret = fs_open(&state.events_file, state.events_path, FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	if (ret != 0) {
		fs_close(&state.raw_file);
		k_mutex_unlock(&state.lock);
		shell_error(shell, "failed to open events file: %d", ret);
		return ret;
	}

	ret = write_text(&state.raw_file, header);
	if (ret == 0) {
		ret = write_text(&state.events_file, event_header);
	}
	if (ret == 0) {
		ret = write_event_locked("run_start");
	}
	if (ret == 0) {
		ret = write_metadata_file(state.run_id, state.fault_label, state.severity);
	}

	if (ret != 0) {
		fs_close(&state.events_file);
		fs_close(&state.raw_file);
		k_mutex_unlock(&state.lock);
		shell_error(shell, "failed to initialize run files: %d", ret);
		return ret;
	}

	state.run_active = true;
	k_mutex_unlock(&state.lock);

	shell_print(shell, "started %s", safe_run_id);
	return 0;
}

static int cmd_fault_on(const struct shell *shell, size_t argc, char **argv)
{
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	k_mutex_lock(&state.lock, K_FOREVER);
	if (!state.run_active) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "no active run");
		return -EINVAL;
	}
	state.fault_active = true;
	ret = write_event_locked("fault_on");
	k_mutex_unlock(&state.lock);

	shell_print(shell, "fault_active=1");
	return ret;
}

static int cmd_fault_off(const struct shell *shell, size_t argc, char **argv)
{
	int ret;

	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	k_mutex_lock(&state.lock, K_FOREVER);
	if (!state.run_active) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "no active run");
		return -EINVAL;
	}
	state.fault_active = false;
	ret = write_event_locked("fault_off");
	k_mutex_unlock(&state.lock);

	shell_print(shell, "fault_active=0");
	return ret;
}

static int cmd_stop(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	k_mutex_lock(&state.lock, K_FOREVER);
	if (!state.run_active) {
		k_mutex_unlock(&state.lock);
		shell_error(shell, "no active run");
		return -EINVAL;
	}

	write_event_locked("run_stop");
	fs_close(&state.events_file);
	fs_close(&state.raw_file);
	state.run_active = false;
	state.fault_active = false;
	k_mutex_unlock(&state.lock);

	shell_print(shell, "stopped");
	return 0;
}

static int cmd_status(const struct shell *shell, size_t argc, char **argv)
{
	ARG_UNUSED(argc);
	ARG_UNUSED(argv);

	k_mutex_lock(&state.lock, K_FOREVER);
	shell_print(shell, "sd_ready=%d run_active=%d fault_active=%d run_id=%s label=%s severity=%d",
		    state.sd_ready ? 1 : 0, state.run_active ? 1 : 0,
		    state.fault_active ? 1 : 0,
		    state.run_active ? state.run_id : "-", state.fault_label, state.severity);
	k_mutex_unlock(&state.lock);
	return 0;
}

SHELL_CMD_REGISTER(start, NULL, "start <run_id> <fault_label> <severity>", cmd_start);
SHELL_CMD_REGISTER(fault_on, NULL, "mark fault active", cmd_fault_on);
SHELL_CMD_REGISTER(fault_off, NULL, "mark fault inactive", cmd_fault_off);
SHELL_CMD_REGISTER(stop, NULL, "stop current run", cmd_stop);
SHELL_CMD_REGISTER(status, NULL, "show logger status", cmd_status);

static void logger_thread(void)
{
	char line[256];
	double voltage_v;
	double current_a;
	double power_w;
	int ret;

	while (true) {
		k_sleep(K_MSEC(LOG_PERIOD_MS));

		k_mutex_lock(&state.lock, K_FOREVER);
		if (!state.run_active) {
			k_mutex_unlock(&state.lock);
			continue;
		}

		ret = read_power_sample(&voltage_v, &current_a, &power_w);
		if (ret != 0) {
			LOG_WRN("INA226 sample failed: %d", ret);
			k_mutex_unlock(&state.lock);
			continue;
		}

		int64_t now = k_uptime_get();
		double elapsed_s = (double)(now - state.run_start_ms) / 1000.0;

		snprintf(line, sizeof(line),
			 "%" PRId64 ",%.3f,%s,%s,%s,%d,%s,%s,%d,%.6f,%.6f,%.6f\n",
			 now, elapsed_s, state.run_id, ROBOT_ID, EXPERT_NAME,
			 state.fault_active ? 1 : 0, state.fault_label,
			 FAULT_SUBSYSTEM, state.severity, voltage_v, current_a, power_w);

		ret = write_text(&state.raw_file, line);
		if (ret != 0) {
			LOG_ERR("CSV write failed: %d", ret);
		}

		k_mutex_unlock(&state.lock);
	}
}

K_THREAD_DEFINE(logger_tid, 4096, logger_thread, NULL, NULL, NULL, 5, 0, 0);

int main(void)
{
	int ret;

	k_mutex_init(&state.lock);
	strncpy(state.fault_label, "healthy", sizeof(state.fault_label) - 1);

	printk("========================================\n");
	printk("Power Expert Logger\n");
	printk("========================================\n");
	printk("Commands: start <run_id> <fault_label> <severity>, fault_on, fault_off, stop, status\n");

	if (!device_is_ready(power_sensor)) {
		LOG_ERR("INA226 device is not ready");
		return 0;
	}

	ret = mount_sd_card();
	if (ret != 0) {
		LOG_ERR("Logger running without SD storage. Fix SD wiring/config and reboot.");
	}

	return 0;
}
