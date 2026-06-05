#include "porter_inference.h"

void porter_normalize_features(const float *raw_features,
			       const struct porter_model_metadata *metadata,
			       float *normalized_features)
{
	for (size_t i = 0; i < metadata->feature_count; i++) {
		const float std = metadata->feature_std[i] == 0.0f ? 1.0f : metadata->feature_std[i];
		normalized_features[i] = (raw_features[i] - metadata->feature_mean[i]) / std;
	}
}

int porter_argmax(const float *values, size_t count)
{
	if (values == 0 || count == 0) {
		return -1;
	}

	int best_index = 0;
	float best_value = values[0];

	for (size_t i = 1; i < count; i++) {
		if (values[i] > best_value) {
			best_value = values[i];
			best_index = (int)i;
		}
	}

	return best_index;
}

void porter_fill_classification_result(const struct porter_model_metadata *metadata,
				       const float *fault_scores,
				       const float *action_scores,
				       struct porter_classification_result *result)
{
	result->fault_index = porter_argmax(fault_scores, metadata->label_count);
	result->action_index = porter_argmax(action_scores, metadata->action_count);
	result->fault_score = result->fault_index >= 0 ? fault_scores[result->fault_index] : 0.0f;
	result->action_score = result->action_index >= 0 ? action_scores[result->action_index] : 0.0f;
	result->fault_label = result->fault_index >= 0 ? metadata->label_names[result->fault_index] : "";
	result->action_label = result->action_index >= 0 ? metadata->action_names[result->action_index] : "";
}
