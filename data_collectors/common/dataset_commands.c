#include "dataset_commands.h"

#include <errno.h>
#include <ff.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zephyr/fs/fat_fs.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/shell/shell.h>

LOG_MODULE_REGISTER(dataset_commands, LOG_LEVEL_INF);

static FATFS fat_fs;
static struct fs_mount_t sd_mount = {
	.type = FS_FATFS,
	.fs_data = &fat_fs,
	.mnt_point = "/SD:",
};

struct dataset_state {
	struct k_mutex lock;
	const struct dataset_config *config;
	bool sd_ready;
	bool run_active;
	bool fault_active;
	int severity;
	int64_t run_start_ms;
	char run_id[DATASET_MAX_RUN_ID_LEN];
	char fault_label[DATASET_MAX_LABEL_LEN];
	char raw_path[DATASET_MAX_PATH_LEN];
	char events_path[DATASET_MAX_PATH_LEN];
	struct fs_file_t raw_file;
	struct fs_file_t events_file;
};

static struct dataset_state state;

static void make_safe_token(char *dst, size_t dst_len, const char *src)
{
	size_t out = 0;

	for (size_t i = 0; src[i] != '\0' && out + 1 < dst_len; i++) {
		char c = src[i];

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

static int write_text(struct fs_file_t *file, const char *text)
{
	size_t len = strlen(text);
	ssize_t written = fs_write(file, text, len);

	return written == len ? 0 : (written < 0 ? (int)written : -EIO);
}

static int ensure_dataset_dirs(const char *expert_name)
{
	char path[DATASET_MAX_PATH_LEN];
	int ret;

	ret = ensure_dir("/SD:/datasets");
	if (ret != 0) {
		return ret;
	}

	snprintf(path, sizeof(path), "/SD:/datasets/%s", expert_name);
	ret = ensure_dir(path);
	if (ret != 0) {
		return ret;
	}

	snprintf(path, sizeof(path), "/SD:/datasets/%s/raw", expert_name);
	ret = ensure_dir(path);
	if (ret != 0) {
		return ret;
	}

	snprintf(path, sizeof(path), "/SD:/datasets/%s/events", expert_name);
	ret = ensure_dir(path);
	if (ret != 0) {
		return ret;
	}

	snprintf(path, sizeof(path), "/SD:/datasets/%s/metadata", expert_name);
	ret = ensure_dir(path);
	if (ret != 0) {
		return ret;
	}

	snprintf(path, sizeof(path), "/SD:/datasets/%s/features", expert_name);
	return ensure_dir(path);
}

static int write_event_locked(const char *event_name)
{
	char line[160];
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

static int write_metadata_locked(void)
{
	struct fs_file_t metadata_file;
	char metadata_path[DATASET_MAX_PATH_LEN];
	char body[640];
	int ret;

	snprintf(metadata_path, sizeof(metadata_path),
		 "/SD:/datasets/%s/metadata/%s.txt",
		 state.config->expert_name, state.run_id);

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
		 "%s",
		 state.run_id, state.config->robot_id, state.config->expert_name,
		 state.fault_label, state.config->fault_subsystem, state.severity,
		 state.config->metadata_extra ? state.config->metadata_extra : "");

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

	ret = ensure_dataset_dirs(state.config->expert_name);
	if (ret != 0) {
		return ret;
	}

	state.sd_ready = true;
	LOG_INF("SD card mounted at %s", sd_mount.mnt_point);
	return 0;
}

int dataset_init(const struct dataset_config *config)
{
	if (config == NULL || config->expert_name == NULL || config->fault_subsystem == NULL ||
	    config->robot_id == NULL || config->raw_header == NULL) {
		return -EINVAL;
	}

	memset(&state, 0, sizeof(state));
	k_mutex_init(&state.lock);
	state.config = config;
	strncpy(state.fault_label, "healthy", sizeof(state.fault_label) - 1);

	return mount_sd_card();
}

bool dataset_is_run_active(void)
{
	bool active;

	k_mutex_lock(&state.lock, K_FOREVER);
	active = state.run_active;
	k_mutex_unlock(&state.lock);
	return active;
}

void dataset_get_snapshot(struct dataset_snapshot *snapshot)
{
	if (snapshot == NULL) {
		return;
	}

	k_mutex_lock(&state.lock, K_FOREVER);
	snapshot->sd_ready = state.sd_ready;
	snapshot->run_active = state.run_active;
	snapshot->fault_active = state.fault_active;
	snapshot->severity = state.severity;
	snapshot->run_start_ms = state.run_start_ms;
	strncpy(snapshot->run_id, state.run_id, sizeof(snapshot->run_id) - 1);
	strncpy(snapshot->fault_label, state.fault_label, sizeof(snapshot->fault_label) - 1);
	snapshot->run_id[sizeof(snapshot->run_id) - 1] = '\0';
	snapshot->fault_label[sizeof(snapshot->fault_label) - 1] = '\0';
	k_mutex_unlock(&state.lock);
}

int dataset_write_common_prefix(char *buf, size_t len, const struct dataset_snapshot *snapshot,
				int64_t timestamp_ms)
{
	double elapsed_s;

	if (buf == NULL || snapshot == NULL || len == 0 || state.config == NULL) {
		return -EINVAL;
	}

	elapsed_s = (double)(timestamp_ms - snapshot->run_start_ms) / 1000.0;
	return snprintf(buf, len, "%" PRId64 ",%.3f,%s,%s,%s,%d,%s,%s,%d",
			timestamp_ms, elapsed_s, snapshot->run_id, state.config->robot_id,
			state.config->expert_name, snapshot->fault_active ? 1 : 0,
			snapshot->fault_label, state.config->fault_subsystem, snapshot->severity);
}

int dataset_write_raw_line(const char *line)
{
	int ret;

	if (line == NULL) {
		return -EINVAL;
	}

	k_mutex_lock(&state.lock, K_FOREVER);
	if (!state.run_active) {
		k_mutex_unlock(&state.lock);
		return -EAGAIN;
	}

	ret = write_text(&state.raw_file, line);
	k_mutex_unlock(&state.lock);
	return ret;
}

int dataset_status(const struct shell *shell)
{
	k_mutex_lock(&state.lock, K_FOREVER);
	shell_print(shell, "sd_ready=%d run_active=%d fault_active=%d run_id=%s label=%s severity=%d",
		    state.sd_ready ? 1 : 0, state.run_active ? 1 : 0,
		    state.fault_active ? 1 : 0,
		    state.run_active ? state.run_id : "-", state.fault_label, state.severity);
	k_mutex_unlock(&state.lock);
	return 0;
}

static int cmd_start(const struct shell *shell, size_t argc, char **argv)
{
	char safe_run_id[DATASET_MAX_RUN_ID_LEN];
	char safe_fault_label[DATASET_MAX_LABEL_LEN];
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

	snprintf(state.raw_path, sizeof(state.raw_path), "/SD:/datasets/%s/raw/%s.csv",
		 state.config->expert_name, state.run_id);
	snprintf(state.events_path, sizeof(state.events_path), "/SD:/datasets/%s/events/%s_events.csv",
		 state.config->expert_name, state.run_id);

	fs_file_t_init(&state.raw_file);
	fs_file_t_init(&state.events_file);

	ret = fs_open(&state.raw_file, state.raw_path, FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	if (ret == 0) {
		ret = fs_open(&state.events_file, state.events_path,
			      FS_O_CREATE | FS_O_WRITE | FS_O_TRUNC);
	}
	if (ret == 0) {
		ret = write_text(&state.raw_file, state.config->raw_header);
	}
	if (ret == 0) {
		ret = write_text(&state.events_file, event_header);
	}
	if (ret == 0) {
		ret = write_event_locked("run_start");
	}
	if (ret == 0) {
		ret = write_metadata_locked();
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
	return dataset_status(shell);
}

SHELL_CMD_REGISTER(start, NULL, "start <run_id> <fault_label> <severity>", cmd_start);
SHELL_CMD_REGISTER(fault_on, NULL, "mark fault active", cmd_fault_on);
SHELL_CMD_REGISTER(fault_off, NULL, "mark fault inactive", cmd_fault_off);
SHELL_CMD_REGISTER(stop, NULL, "stop current run", cmd_stop);
SHELL_CMD_REGISTER(status, NULL, "show logger status", cmd_status);
