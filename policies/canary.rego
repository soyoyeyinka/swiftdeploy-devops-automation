package swiftdeploy.canary

import rego.v1

default decision := {
  "allow": false,
  "domain": "canary",
  "reason": "Canary policy did not complete evaluation.",
  "violations": ["no policy decision was produced"]
}

error_rate_violation if {
  input.metrics.error_rate > input.thresholds.max_error_rate
}

latency_violation if {
  input.metrics.p99_latency_seconds > input.thresholds.max_p99_latency_seconds
}

violations contains msg if {
  error_rate_violation
  msg := sprintf("Error rate is %v, which is above the allowed %v.", [input.metrics.error_rate, input.thresholds.max_error_rate])
}

violations contains msg if {
  latency_violation
  msg := sprintf("P99 latency is %v seconds, which is above the allowed %v seconds.", [input.metrics.p99_latency_seconds, input.thresholds.max_p99_latency_seconds])
}

decision := {
  "allow": true,
  "domain": "canary",
  "reason": "Canary policy passed. Error rate and P99 latency are within the allowed limits.",
  "violations": []
} if {
  count(violations) == 0
}

decision := {
  "allow": false,
  "domain": "canary",
  "reason": "Canary policy blocked this promotion.",
  "violations": violations
} if {
  count(violations) > 0
}
