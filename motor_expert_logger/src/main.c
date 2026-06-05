#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>

int main(void)
{
    printk("========================================\n");
    printk("Motor Expert Logger\n");
    printk("========================================\n");
    printk("Collects motor response telemetry for motor-side fault detection.\n");
    printk("Skeleton generated.\n");

    while (1) {
        k_sleep(K_SECONDS(1));
    }

    return 0;
}
