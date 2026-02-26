# PT Teleconsult Routing System Documentation

## Overview

The PT Teleconsult Routing System is designed to route all private teleconsultations to a dedicated PT account regardless of branch or delivery method. This system enables centralizing teleconsult management while maintaining flexibility in appointment types and branch assignments.

## Configuration

The routing system uses a configuration-based approach with the `TELECONSULT_BRANCH_ROUTING` setting in the system configuration. The configuration structure is as follows:

```json
{
  "sgimed_branch_id": "PT", 
  "state": "off | test | on",
  "delivery_sgimed_appointment_type_id": "<PT branch telemed appointment_type_id>",
  "pickup_sgimed_appointment_type_id": {
    "<sgimed_branch_id>": "<PT branch id appointment_type_id>",
  }
}
```

### Configuration Parameters

- **sgimed_branch_id**: The SGiMed branch ID to route teleconsults to
- **state**: One of three values:
  - **off**: PT routing is disabled
  - **test**: PT routing only applies to test users
  - **on**: PT routing applies to all private patients
- **delivery_sgimed_appointment_type_id**: The appointment type ID to use for delivery teleconsults
- **pickup_sgimed_appointment_type_id**: A map of branch IDs to appointment type IDs for pickup teleconsults

## Implementation Details

The routing system is implemented in the `get_sgimed_telemed_routing_params` function in `utils/system_config.py`. This function:

1. Determines if the teleconsult is eligible for routing based on:
   - Whether PT routing is enabled
   - Patient type (only private patients)
   - Test user status (if in test mode)
2. If eligible, routes the teleconsult to the PT branch with the appropriate appointment type
3. Returns routing parameters for queue creation, including:
   - `branch_id`: The branch to route to
   - `original_branch_id`: The original branch (for reference)
   - `appointment_type_id`: The appointment type to use

## Error Handling

The system includes robust error handling and logging:

- Validates configuration parameters and logs errors for missing values
- Preserves original branch ID for reference and troubleshooting
- Logs all routing decisions and parameters for traceability
- Falls back to default routing when configuration is invalid or incomplete
- Includes defensive error handling in the teleconsult flow to prevent failures
- Reports detailed errors with context to help diagnose issues

## Example Routing Scenarios

### Scenario 1: Delivery for Private Patient

For a private patient selecting delivery:
- Routes to PT branch (`pt_branch_id`)
- Uses the delivery appointment type (`delivery_sgimed_appointment_type_id`)

### Scenario 2: Pickup for Private Patient

For a private patient selecting pickup from branch SG1:
- Routes to PT branch (`pt_branch_id`)
- Uses SG1's pickup appointment type from the mapping (`pickup_sgimed_appointment_type_id["SG1"]`)

### Scenario 3: Non-Private Patient

For a corporate patient:
- Does not apply PT routing
- Uses original branch and appointment type

### Scenario 4: Test Mode

In test mode:
- Only routes test users to PT branch
- Non-test users follow regular routing

## Monitoring and Troubleshooting

- All routing decisions are logged with INFO level
- Configuration validation errors are logged with ERROR level
- The teleconsult flow includes exception handling with detailed error logs
- Each teleconsult record preserves its original branch for audit purposes

## Integration Points

- `prepayment_success_webhook` in `routers/patient/actions/teleconsult_flow_backend.py`
- `create_queue` function in `utils/integrations/sgimed.py`

## Extension Points

The system is designed for easy extension:

1. Adding new branches by updating the `pickup_sgimed_appointment_type_id` mapping
2. Supporting new patient types by modifying the eligibility logic
3. Adding new routing criteria by extending the configuration structure

## Testing

A comprehensive test suite is available in `tests/test_teleconsult_pt_routing.py` covering:

### Test Scenarios

1. **Private Patient (Standard Mode)**
   - **Configuration**: Routing enabled with `state: "on"`
   - **Patient Type**: Private patient
   - **Collection Method**: Pickup
   - **Expected Behavior**: Routes to PT branch with pickup appointment type
   - **Test Function**: `test_private_patient`

2. **Private Patient (Test User - Delivery)**
   - **Configuration**: Routing enabled with `state: "test"`
   - **Patient Type**: Private patient who is a test user
   - **Collection Method**: Delivery
   - **Expected Behavior**: Routes to PT branch with delivery appointment type
   - **Test Function**: `test_private_patient_test_user_delivery`

3. **Private Patient (Test User - Pickup)**
   - **Configuration**: Routing enabled with `state: "test"`
   - **Patient Type**: Private patient who is a test user
   - **Collection Method**: Pickup
   - **Expected Behavior**: Routes to PT branch with pickup appointment type
   - **Test Function**: `test_private_patient_test_user_pickup`

4. **Private Patient (Non-Test User in Test Mode)**
   - **Configuration**: Routing enabled with `state: "test"`
   - **Patient Type**: Private patient who is NOT a test user
   - **Collection Method**: Pickup
   - **Expected Behavior**: Does NOT route to PT branch (uses original branch)
   - **Test Function**: `test_private_patient_non_test_user_in_test_mode`

5. **Migrant Worker Patient**
   - **Configuration**: Routing enabled with `state: "on"`
   - **Patient Type**: Migrant worker
   - **Collection Method**: Pickup
   - **Expected Behavior**: Does NOT route to PT branch (uses original branch)
   - **Test Function**: `test_migrant_worker`

6. **Routing Disabled**
   - **Configuration**: Routing disabled (config is null)
   - **Patient Type**: Private patient
   - **Collection Method**: Pickup
   - **Expected Behavior**: Uses default branch and appointment type
   - **Test Function**: `test_when_routing_disabled`

### Running Tests

To run the tests:

```bash
# Run all teleconsult PT routing tests
uv run pytest tests/test_teleconsult_pt_routing.py

# Run a specific test
uv run pytest tests/test_teleconsult_pt_routing.py::test_private_patient
```

### Test Implementation Pattern

Each test follows a consistent pattern:
1. **Setup**: Configure mocks for test scenario
2. **Execute**: Call the routing function
3. **Assert**: Verify routing parameters match expected behavior

Tests use patching to isolate the routing function from external dependencies and verify interaction patterns.
