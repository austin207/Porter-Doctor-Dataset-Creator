#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

int main(void)
{
    printk("========================================\n");
    printk("ESP32 Expert Logger\n");
    printk("========================================\n");
    printk("Collects controller health telemetry for ESP32 reset, heartbeat and communication fault detection.\n");
    printk("Skeleton generated.\n");

    while (1) {
        k_sleep(K_SECONDS(1));
    }

    return 0;
}
