#ifndef PORTER_INFERENCE_H
#define PORTER_INFERENCE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

struct porter_model_metadata {
	const unsigned char *model_data;
	size_t model_data_len;
	const char *const *feature_names;
	const float *feature_mean;
	const float *feature_std;
	size_t feature_count;
	const char *const *label_names;
	size_t label_count;
	const char *const *action_names;
	size_t action_count;
	float anomaly_threshold;
};

struct porter_classification_result {
	int fault_index;
	int action_index;
	float fault_score;
	float action_score;
	const char *fault_label;
	const char *action_label;
};

void porter_normalize_features(const float *raw_features,
			       const struct porter_model_metadata *metadata,
			       float *normalized_features);

int porter_argmax(const float *values, size_t count);

void porter_fill_classification_result(const struct porter_model_metadata *metadata,
				       const float *fault_scores,
				       const float *action_scores,
				       struct porter_classification_result *result);

#ifdef __cplusplus
}
#endif

#endif
