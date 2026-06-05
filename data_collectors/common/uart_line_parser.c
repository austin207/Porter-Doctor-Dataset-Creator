#include "uart_line_parser.h"

#include <string.h>
#include <zephyr/drivers/uart.h>

void uart_line_parser_init(struct uart_line_parser *parser, const struct device *uart,
			   char *buffer, size_t buffer_len, uart_line_callback_t callback,
			   void *user_data)
{
	memset(parser, 0, sizeof(*parser));
	parser->uart = uart;
	parser->buffer = buffer;
	parser->buffer_len = buffer_len;
	parser->callback = callback;
	parser->user_data = user_data;
}

void uart_line_parser_poll(struct uart_line_parser *parser)
{
	uint8_t ch;

	if (parser == NULL || parser->uart == NULL || parser->buffer == NULL ||
	    parser->buffer_len < 2) {
		return;
	}

	while (uart_poll_in(parser->uart, &ch) == 0) {
		if (ch == '\r') {
			continue;
		}

		if (ch == '\n') {
			parser->buffer[parser->pos] = '\0';
			if (parser->pos > 0 && parser->callback != NULL) {
				parser->callback(parser->buffer, parser->user_data);
			}
			parser->pos = 0;
			continue;
		}

		if (parser->pos + 1 >= parser->buffer_len) {
			parser->pos = 0;
			parser->rx_errors++;
			continue;
		}

		parser->buffer[parser->pos++] = (char)ch;
	}
}

unsigned int uart_line_parser_errors(const struct uart_line_parser *parser)
{
	return parser == NULL ? 0U : parser->rx_errors;
}
