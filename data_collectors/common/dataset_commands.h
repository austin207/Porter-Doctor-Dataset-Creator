#ifndef PORTER_DATASET_COMMANDS_H
#define PORTER_DATASET_COMMANDS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <zephyr/fs/fs.h>
#include <zephyr/shell/shell.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DATASET_MAX_RUN_ID_LEN 48
#define DATASET_MAX_LABEL_LEN 32
#define DATASET_MAX_PATH_LEN 160
#define DATASET_COMMON_COLUMNS \
	"timestamp_ms,elapsed_s,run_id,robot_id,expert_name,fault_active," \
	"fault_label,fault_subsystem,severity"

struct dataset_config {
	const char *expert_name;
	const char *fault_subsystem;
	const char *robot_id;
	const char *raw_header;
	const char *metadata_extra;
};

struct dataset_snapshot {
	bool sd_ready;
	bool run_active;
	bool fault_active;
	int severity;
	int64_t run_start_ms;
	char run_id[DATASET_MAX_RUN_ID_LEN];
	char fault_label[DATASET_MAX_LABEL_LEN];
};

int dataset_init(const struct dataset_config *config);
bool dataset_is_run_active(void);
void dataset_get_snapshot(struct dataset_snapshot *snapshot);
int dataset_write_raw_line(const char *line);
int dataset_write_common_prefix(char *buf, size_t len, const struct dataset_snapshot *snapshot,
				int64_t timestamp_ms);
int dataset_status(const struct shell *shell);

#ifdef __cplusplus
}
#endif

#endif
