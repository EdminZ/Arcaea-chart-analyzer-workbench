# Editing difficulty functions

## A first experiment

1. Generate/open the synthetic demo.
2. Difficulty Functions → Load active. This loads a draft from the current model.
3. Change tap_power from 1.0 to 1.2 in the parameters. Use the existing parameter controls, or edit JSON and choose Refresh controls from JSON.
4. Plot the response and choose Compare on chart. This compares a trial without replacing the active result.
5. Save draft if you want to keep editing later. To adopt it, choose Validate & activate, then Update current chart (or batch Update difficulty).
6. To return, use Restore version and recalculate. Export definition saves a portable model JSON.

Because both responses share a normalization reference, changing one curve can rescale the other. Do not assume that increasing one parameter increases every chart metric. Inspect the comparison.

## What the axes mean

The response graph uses corrected speed v = sqrt(dx² + (vertical_scale*dy)²) / interval_seconds. Its tap channel represents transfer movement between successive contacts; it is not the frequency of tapping. Input frequency is computed separately. Arc response describes movement during a sustained contact.

Sequence y is already (1 + 4.5*AFF_y)/8.5. vertical_scale is an additional factor, default 0.5, not measured hardware geometry. Speed cap / X max defaults to 4 and affects calculations as well as the plot. Shared response normalization defaults on and uses maximum 1; integrated chart metrics can exceed 1. Capped/clipped intervals appear in warnings.

For context, a corrected displacement of 0.2 over 0.1 seconds gives speed 2. A displacement of 0.3 over 0.08 seconds gives 3.75. These are examples, not limits on legal gameplay.

## Controls by effect

| Setting | Changes |
|---|---|
| Response expression or piecewise curve | Intensity assigned to speed |
| vertical_scale | Movement distances and low-motion classification |
| speed_limit | Saturation and graph range |
| frequency_window_ms / movement_window_ms | Signal aggregation windows |
| peak_min_ms / near_peak_ratio | Peak duration qualification |
| arc_threshold | Low-motion path-length threshold for volume handling |
| Trajectory smoothing / axis view | Display only |
| Recognition tolerance/profile | Execution inference; rerun recognition separately |

The JSON metrics map defines aggregations; default note=max(frequency_mean,frequency_mode), Peak=frequency_peak, distance=total_weight, movement=movement_peak and Arc=arc_weight. Read app/model2.py before introducing a new raw measurement. The evaluator supports restricted expressions and piecewise curves, not arbitrary Python. Keep movement response zero at zero speed.

## Reproducible comparisons

Save the model JSON, sequence and recognition profile with exported results. A reference difficulty CSV does not calibrate these functions. Dataset normalization and a calibrated overall rating remain research tasks. Use held-out charts if tuning against player judgments; record alternative acceptable executions rather than declaring every automatic label correct.
