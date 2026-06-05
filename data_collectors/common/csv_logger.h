#ifndef PORTER_CSV_LOGGER_H
#define PORTER_CSV_LOGGER_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int csv_append_int(char *buf, size_t len, int *offset, int value);
int csv_append_i64(char *buf, size_t len, int *offset, long long value);
int csv_append_double(char *buf, size_t len, int *offset, double value);
int csv_append_bool(char *buf, size_t len, int *offset, bool value);

#ifdef __cplusplus
}
#endif

#endif
