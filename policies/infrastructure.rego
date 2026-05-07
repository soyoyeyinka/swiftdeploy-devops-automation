package swiftdeploy.infrastructure

import rego.v1

default decision := {
  "allow": false,
  "domain": "infrastructure",
  "reason": "Infrastructure policy did not complete evaluation.",
  "violations": ["no policy decision was produced"]
}

disk_violation if {
  input.host.disk_free_gb < input.thresholds.min_disk_free_gb
}

cpu_violation if {
  input.host.cpu_load > input.thresholds.max_cpu_load
}

violations contains msg if {
  disk_violation
  msg := sprintf("Disk free is %vGB, which is below the required %vGB.", [input.host.disk_free_gb, input.thresholds.min_disk_free_gb])
}

violations contains msg if {
  cpu_violation
  msg := sprintf("CPU load is %v, which is above the allowed %v.", [input.host.cpu_load, input.thresholds.max_cpu_load])
}

decision := {
  "allow": true,
  "domain": "infrastructure",
  "reason": "Infrastructure policy passed. Disk and CPU are within the allowed limits.",
  "violations": []
} if {
  count(violations) == 0
}

decision := {
  "allow": false,
  "domain": "infrastructure",
  "reason": "Infrastructure policy blocked this action.",
  "violations": violations
} if {
  count(violations) > 0
}
