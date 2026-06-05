#include "csv_logger.h"

#include <stdbool.h>
#include <stdio.h>

static int append_checked(char *buf, size_t len, int *offset, int written)
{
	if (written < 0 || *offset + written >= (int)len) {
		return -1;
	}

	*offset += written;
	return 0;
}

int csv_append_int(char *buf, size_t len, int *offset, int value)
{
	return append_checked(buf, len, offset, snprintf(buf + *offset, len - *offset, ",%d", value));
}

int csv_append_i64(char *buf, size_t len, int *offset, long long value)
{
	return append_checked(buf, len, offset, snprintf(buf + *offset, len - *offset, ",%lld", value));
}

int csv_append_double(char *buf, size_t len, int *offset, double value)
{
	return append_checked(buf, len, offset, snprintf(buf + *offset, len - *offset, ",%.6f", value));
}

int csv_append_bool(char *buf, size_t len, int *offset, bool value)
{
	return csv_append_int(buf, len, offset, value ? 1 : 0);
}
