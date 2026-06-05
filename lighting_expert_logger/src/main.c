#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

int main(void)
{
    printk("========================================\n");
    printk("Lighting Expert Logger\n");
    printk("========================================\n");
    printk("Collects lighting-system telemetry for LED, driver and brightness mismatch fault detection.\n");
    printk("Skeleton generated.\n");

    while (1) {
        k_sleep(K_SECONDS(1));
    }

    return 0;
}
