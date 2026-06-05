#ifndef PORTER_UART_LINE_PARSER_H
#define PORTER_UART_LINE_PARSER_H

#include <stddef.h>
#include <zephyr/device.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*uart_line_callback_t)(const char *line, void *user_data);

struct uart_line_parser {
	const struct device *uart;
	char *buffer;
	size_t buffer_len;
	size_t pos;
	uart_line_callback_t callback;
	void *user_data;
	unsigned int rx_errors;
};

void uart_line_parser_init(struct uart_line_parser *parser, const struct device *uart,
			   char *buffer, size_t buffer_len, uart_line_callback_t callback,
			   void *user_data);
void uart_line_parser_poll(struct uart_line_parser *parser);
unsigned int uart_line_parser_errors(const struct uart_line_parser *parser);

#ifdef __cplusplus
}
#endif

#endif
