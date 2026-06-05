#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#include "anomaly_detector_bundle.h"
#include "esp32_expert_bundle.h"
#include "lighting_expert_bundle.h"
#include "motor_driver_expert_bundle.h"
#include "motor_expert_bundle.h"
#include "porter_inference.h"
#include "power_expert_bundle.h"
#include "router_bundle.h"

struct named_model {
	const char *name;
	const struct porter_model_metadata *metadata;
};

static const struct named_model models[] = {
	{ "power_expert", &porter_power_expert_metadata },
	{ "motor_expert", &porter_motor_expert_metadata },
	{ "motor_driver_expert", &porter_motor_driver_expert_metadata },
	{ "esp32_expert", &porter_esp32_expert_metadata },
	{ "lighting_expert", &porter_lighting_expert_metadata },
	{ "router", &porter_router_metadata },
	{ "anomaly_detector", &porter_anomaly_detector_metadata },
};

int main(void)
{
	printk("Porter Zephyr inference smoke app\n");

	for (size_t i = 0; i < ARRAY_SIZE(models); i++) {
		const struct porter_model_metadata *metadata = models[i].metadata;

		printk("%s: model=%u bytes features=%u labels=%u actions=%u threshold=%d.%06d\n",
		       models[i].name,
		       (unsigned int)metadata->model_data_len,
		       (unsigned int)metadata->feature_count,
		       (unsigned int)metadata->label_count,
		       (unsigned int)metadata->action_count,
		       (int)metadata->anomaly_threshold,
		       (int)((metadata->anomaly_threshold - (int)metadata->anomaly_threshold) * 1000000.0f));
	}

	return 0;
}
