# Cleanup and Teardown Boundary

`opspilot cleanup plan` is intentionally non-executing. It returns the required deletion order and
states that destructive execution is disabled and separately approved. It never invokes Terraform,
Google Cloud, or a shell command.

```powershell
uv run opspilot cleanup plan --format summary
```

An authorized operator may later turn the documented order into reviewed `terraform plan -destroy`
artifacts. If M8 is enabled, the faulty profile must first be reset, outstanding approval callbacks
must expire, and the control API, Workflow, executor, TTL policies, and named Firestore database
must be handled as a separate checkpoint. Agent Runtime, demo services, knowledge resources, IAM,
remote state, and bootstrap resources require separate checkpoints; remote state is retained until
environment absence is verified. No destroy or apply command is part of the automated portfolio
workflow.
