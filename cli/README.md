# CLI Tools

Command-line interface tools for testing and managing the backend-patient-app.

## Available Tools

### 1. Service Group Testing Tools
### 2. Service Testing Tools
### 3. Corporate Code Testing Tools
### 4. Onsite Branch Testing Tools

## Service Group Testing Tools

### Overview

A comprehensive CLI testing suite for the Service Group CRUD operations in the appointment module.

This testing module provides a CLI application that:
- Tests all Service Group CRUD operations (Create, Read, Update, Delete)
- Verifies API responses match expected behavior
- Validates database records are correctly saved and updated
- Provides interactive user input for test data
- Includes cleanup functionality to remove test data

### Features

- **Complete CRUD Testing**: Tests all five operations (Create, Get, List, Update, Delete)
- **Database Verification**: Checks that API operations correctly modify database records
- **Interactive CLI**: Beautiful terminal interface with Rich formatting
- **Multiple Commands**: Different testing modes for different use cases
- **Auto-cleanup**: Automatically removes test data after testing (configurable)
- **Error Handling**: Comprehensive error handling and reporting

### Installation

```bash
# Navigate to the backend-patient-app directory
cd backend-patient-app

# Install dependencies including dev dependencies (typer, rich)
uv sync --dev
```

### Usage

#### Full CRUD Test Suite

Run the complete test suite with interactive prompts:

```bash
uv run cli/service_group_tester.py test-crud
```

Options:
- `--base-url`: API server URL (default: /api/admin/appointments/v1)
- `--auto-cleanup/--no-auto-cleanup`: Control automatic cleanup (default: enabled)

#### List Only

Just test the LIST operation to see existing service groups:

```bash
uv run cli/service_group_tester.py list-only
```

#### Database Verification

Verify a specific service group exists in the database:

```bash
uv run cli/service_group_tester.py verify-db <service-group-id>
```

#### Edge Cases Reference

Display comprehensive edge cases and testing scenarios:

```bash
uv run cli/service_group_tester.py edge-cases
```

#### Help

Get help for any command:

```bash
uv run cli/service_group_tester.py --help
uv run cli/service_group_tester.py test-crud --help
```

### Test Flow

The full CRUD test suite follows this flow:

1. **CREATE**: 
   - Prompts user for service group data
   - Calls POST `/service-groups` API
   - Verifies API response and database record

2. **GET**: 
   - Calls GET `/service-groups/{id}` API
   - Displays service group details in a table

3. **LIST**: 
   - Calls GET `/service-groups` API
   - Shows all service groups in a formatted table

4. **UPDATE** (optional):
   - Prompts user for fields to update
   - Calls PUT `/service-groups/{id}` API
   - Verifies database record reflects changes

5. **DELETE** (optional):
   - Calls DELETE `/service-groups/{id}` API
   - Verifies record is removed from database

6. **CLEANUP**: 
   - Automatically removes any test records created during testing

### Service Group Data Structure

The tester handles these Service Group fields:

- **name**: Service group name (required)
- **description**: Optional description
- **index**: Sorting order (integer)
- **icon**: Icon identifier (string)
- **duration**: Duration in minutes (integer)
- **type**: Service group type (no_detail, single, multiple)
- **restricted_branches**: List of branch codes (optional)

### Error Handling

The tester includes comprehensive error handling for:

- Database connection failures
- API server connectivity issues
- Invalid responses
- Missing dependencies
- User interruption (Ctrl+C)

### Dependencies

- **typer**: Modern CLI framework
- **rich**: Beautiful terminal formatting
- **fastapi.testclient**: For API testing
- **sqlalchemy**: Database ORM for verification

### Integration

This module imports directly from the parent backend-patient-app modules:
- Database models (`AppointmentServiceGroup`, `AppointmentServiceGroupType`)
- Session management (`SessionLocal`)
- FastAPI app (`main.app`)

Make sure the backend application is properly configured with database access before running tests.

## Service Testing Tools

### Overview

A comprehensive CLI testing suite for the Service CRUD operations in the appointment module.

This testing module provides a CLI application that:
- Tests all Service CRUD operations (Create, Read, Update, Delete)
- Verifies API responses match expected behavior
- Validates database records are correctly saved and updated
- Provides interactive user input for test data with service group selection
- Includes cleanup functionality to remove test data
- Supports SGiMed inventory linking and test configuration

### Features

- **Complete CRUD Testing**: Tests all five operations (Create, Get, List, Update, Delete)
- **Database Verification**: Checks that API operations correctly modify database records
- **Interactive CLI**: Beautiful terminal interface with Rich formatting
- **Service Group Integration**: Automatically fetches and displays available service groups
- **SGiMed Integration**: Support for linking services to SGiMed inventory items
- **Test Configuration**: Support for adding test items with exclusions
- **Multiple Commands**: Different testing modes for different use cases
- **Auto-cleanup**: Automatically removes test data after testing (configurable)
- **Error Handling**: Comprehensive error handling and reporting

### Usage

#### Full CRUD Test Suite

Run the complete test suite with interactive prompts:

```bash
uv run cli/service_tester.py test-crud
```

Options:
- `--base-url`: API server URL (default: /api/admin/appointments/v1)
- `--auto-cleanup/--no-auto-cleanup`: Control automatic cleanup (default: enabled)

#### List Only

Just test the LIST operation to see existing services:

```bash
uv run cli/service_tester.py list-only

# Filter by service group
uv run cli/service_tester.py list-only --group-id <service-group-id>
```

#### Database Verification

Verify a specific service exists in the database:

```bash
uv run cli/service_tester.py verify-db <service-id>
```

#### Help

Get help for any command:

```bash
uv run cli/service_tester.py --help
uv run cli/service_tester.py test-crud --help
```

### Test Flow

The full CRUD test suite follows this flow:

1. **CREATE**: 
   - Prompts user for service data including service group selection
   - Shows available service groups and SGiMed inventories
   - Calls POST `/services` API
   - Verifies API response and database record

2. **GET**: 
   - Calls GET `/services/{id}` API
   - Displays service details in a table

3. **LIST**: 
   - Calls GET `/services` API
   - Shows all services with pricing and group information in a formatted table

4. **UPDATE** (optional):
   - Prompts user for fields to update
   - Calls PUT `/services/{id}` API
   - Verifies database record reflects changes

5. **DELETE** (optional):
   - Calls DELETE `/services/{id}` API
   - Verifies record is removed from database

6. **CLEANUP**: 
   - Automatically removes any test records created during testing

### Service Data Structure

The tester handles these Service fields:

- **name**: Service name (required)
- **prepayment_price**: Price for prepayment (float)
- **display_price**: Display price (float)
- **index**: Sorting order (integer)
- **min_booking_ahead_days**: Minimum days to book ahead (integer, default 2)
- **sgimed_inventory_id**: Link to SGiMed inventory (optional)
- **restricted_branches**: List of branch codes (optional)
- **tests**: List of test items with exclusions (optional)
- **group_id**: Parent service group ID (required)

### Prerequisites

Before testing services, ensure you have:
1. At least one Service Group created (use `service_group_tester.py` first)
2. SGiMed inventory data if you plan to link services to inventory items
3. Valid branch codes if using restricted branches

### Dependencies

- **typer**: Modern CLI framework
- **rich**: Beautiful terminal formatting
- **fastapi.testclient**: For API testing
- **sqlalchemy**: Database ORM for verification

### Integration

This module imports directly from the parent backend-patient-app modules:
- Database models (`AppointmentService`, `AppointmentServiceGroup`, `SGiMedInventory`)
- Session management (`SessionLocal`)
- FastAPI app (`main.app`)

## Corporate Code Testing Tools

### Overview

A comprehensive CLI testing suite for the AppointmentCorporateCode CRUD operations in the appointment module.

This testing module provides a CLI application that:
- Tests all AppointmentCorporateCode CRUD operations (Create, Read, Update, Delete)
- Verifies API responses match expected behavior
- Validates database records are correctly saved and updated
- Provides interactive user input for test data with service group and branch integration
- Includes cleanup functionality to remove test data
- Supports survey configuration and validity period management

### Features

- **Complete CRUD Testing**: Tests all five operations (Create, Get, List, Update, Delete)
- **Database Verification**: Checks that API operations correctly modify database records
- **Interactive CLI**: Beautiful terminal interface with Rich formatting
- **Service Group Integration**: Link corporate codes to service groups during testing
- **Survey Management**: Test patient and corporate survey configurations
- **Validity Period Testing**: Support for date-based validity periods
- **Relationship Verification**: Check linked service groups and onsite branches
- **Multiple Commands**: Different testing modes for different use cases
- **Auto-cleanup**: Automatically removes test data after testing (configurable)
- **Error Handling**: Comprehensive error handling and reporting

### Usage

#### Full CRUD Test Suite

Run the complete test suite with interactive prompts:

```bash
uv run cli/corporate_code_tester.py test-crud
```

Options:
- `--base-url`: API server URL (default: /api/admin/appointments/v1)
- `--auto-cleanup/--no-auto-cleanup`: Control automatic cleanup (default: enabled)
- `--show-edge-cases`: Display edge cases before testing (default: enabled)

#### List Only

Just test the LIST operation to see existing corporate codes:

```bash
uv run cli/corporate_code_tester.py list-only
```

#### Database Verification

Verify a specific corporate code exists in the database:

```bash
uv run cli/corporate_code_tester.py verify-db <corporate-code-id>
```

#### Edge Cases Reference

Display comprehensive edge cases and testing scenarios:

```bash
uv run cli/corporate_code_tester.py edge-cases
```

#### Help

Get help for any command:

```bash
uv run cli/corporate_code_tester.py --help
uv run cli/corporate_code_tester.py test-crud --help
```

### Test Flow

The full CRUD test suite follows this flow:

1. **CREATE**: 
   - Prompts user for corporate code data including surveys and validity periods
   - Shows available service groups for linking
   - Calls POST `/corporate-codes` API
   - Verifies API response and database record

2. **GET**: 
   - Calls GET `/corporate-codes/{id}` API
   - Displays corporate code details in a table

3. **LIST**: 
   - Calls GET `/corporate-codes` API
   - Shows all corporate codes with status and validity information in a formatted table

4. **UPDATE** (optional):
   - Prompts user for fields to update
   - Calls PUT `/corporate-codes/{id}` API
   - Verifies database record reflects changes

5. **DELETE** (optional):
   - Calls DELETE `/corporate-codes/{id}` API
   - Verifies record is removed from database

6. **CLEANUP**: 
   - Automatically removes any test records created during testing

### Corporate Code Data Structure

The tester handles these AppointmentCorporateCode fields:

- **code**: Unique corporate code identifier (required)
- **organization**: Organization name (required)
- **patient_survey**: JSON object defining patient survey questions (required)
- **corporate_survey**: JSON object defining corporate survey questions (required)
- **valid_from**: Start date for validity period (optional)
- **valid_to**: End date for validity period (optional)
- **is_active**: Boolean flag for active status (default: true)
- **service_group_ids**: List of service group IDs to link (optional)

### Survey Structure

The tester supports creating sample survey configurations with the following structure:

```json
{
  "questions": [
    {
      "id": "field_id",
      "type": "text|select|number|date",
      "label": "Display Label",
      "required": true|false,
      "options": ["option1", "option2"] // for select type
    }
  ]
}
```

### Error Handling

The tester includes comprehensive error handling for:

- Database connection failures
- API server connectivity issues
- Invalid responses
- Duplicate corporate codes
- Invalid survey JSON structures
- Missing dependencies
- User interruption (Ctrl+C)

### Dependencies

- **typer**: Modern CLI framework
- **rich**: Beautiful terminal formatting
- **fastapi.testclient**: For API testing
- **sqlalchemy**: Database ORM for verification

### Integration

This module imports directly from the parent backend-patient-app modules:
- Database models (`AppointmentCorporateCode`, `AppointmentServiceGroup`, `AppointmentOnsiteBranch`, `Branch`)
- Session management (`SessionLocal`)
- FastAPI app (`main.app`)

Make sure the backend application is properly configured with database access before running tests.

## Onsite Branch Testing Tools

### Overview

A comprehensive CLI testing suite for the AppointmentOnsiteBranch CRUD operations in the appointment module.

This testing module provides a CLI application that:
- Tests all AppointmentOnsiteBranch CRUD operations (Create, Read, Update, Delete)
- Verifies API responses match expected behavior
- Validates database records are correctly saved and updated
- Provides interactive user input for test data with branch and corporate code selection
- Includes cleanup functionality to remove test data
- Supports date range validation and timezone handling
- Provides filtering capabilities for listing operations

### Features

- **Complete CRUD Testing**: Tests all five operations (Create, Get, List, Update, Delete)
- **Database Verification**: Checks that API operations correctly modify database records
- **Interactive CLI**: Beautiful terminal interface with Rich formatting
- **Branch Integration**: Select from available branches during testing
- **Corporate Code Integration**: Link onsite branches to corporate codes
- **Date Range Management**: Interactive date selection with validation
- **Filtering Support**: List onsite branches by corporate code or branch
- **Timezone Handling**: Proper Singapore timezone conversion
- **Relationship Verification**: Check linked branches and corporate codes
- **Multiple Commands**: Different testing modes for different use cases
- **Auto-cleanup**: Automatically removes test data after testing (configurable)
- **Error Handling**: Comprehensive error handling and reporting

### Usage

#### Full CRUD Test Suite

Run the complete test suite with interactive prompts:

```bash
uv run cli/onsite_branch_tester.py test-crud
```

Options:
- `--base-url`: API server URL (default: /api/admin/appointments/v1)
- `--auto-cleanup/--no-auto-cleanup`: Control automatic cleanup (default: enabled)
- `--show-edge-cases`: Display edge cases before testing (default: enabled)

#### List Only

Just test the LIST operation to see existing onsite branches:

```bash
# List all onsite branches
uv run cli/onsite_branch_tester.py list-only

# Filter by corporate code
uv run cli/onsite_branch_tester.py list-only --corporate-code-id <corporate-code-id>

# Filter by branch
uv run cli/onsite_branch_tester.py list-only --branch-id <branch-id>
```

#### Database Verification

Verify a specific onsite branch exists in the database:

```bash
uv run cli/onsite_branch_tester.py verify-db <onsite-branch-id>
```

#### Edge Cases Reference

Display comprehensive edge cases and testing scenarios:

```bash
uv run cli/onsite_branch_tester.py edge-cases
```

#### Help

Get help for any command:

```bash
uv run cli/onsite_branch_tester.py --help
uv run cli/onsite_branch_tester.py test-crud --help
```

### Test Flow

The full CRUD test suite follows this flow:

1. **CREATE**: 
   - Prompts user for onsite branch data including branch and corporate code selection
   - Shows available branches and corporate codes for selection
   - Validates date ranges and timezone conversion
   - Calls POST `/onsite-branches` API
   - Verifies API response and database record

2. **GET**: 
   - Calls GET `/onsite-branches/{id}` API
   - Displays onsite branch details in a table

3. **LIST**: 
   - Calls GET `/onsite-branches` API (unfiltered)
   - Shows all onsite branches with branch, corporate code, and date information in a formatted table

4. **FILTERED LIST** (optional):
   - Tests filtering by corporate code ID
   - Tests filtering by branch ID
   - Demonstrates query parameter usage

5. **UPDATE** (optional):
   - Prompts user for fields to update
   - Calls PUT `/onsite-branches/{id}` API
   - Verifies database record reflects changes

6. **DELETE** (optional):
   - Calls DELETE `/onsite-branches/{id}` API
   - Verifies record is removed from database

7. **CLEANUP**: 
   - Automatically removes any test records created during testing

### Onsite Branch Data Structure

The tester handles these AppointmentOnsiteBranch fields:

- **branch_id**: Branch UUID (required, selected from available branches)
- **corporate_code_id**: Corporate code UUID (required, selected from active corporate codes)
- **header**: Optional descriptive header/title for the onsite branch
- **start_date**: Start date and time for the onsite branch period (required)
- **end_date**: End date and time for the onsite branch period (required)

### Date Handling

The tester includes comprehensive date handling:

- **Interactive Date Input**: User-friendly date prompts with default values
- **Validation**: Ensures start_date < end_date
- **Timezone Support**: Automatic Singapore timezone conversion
- **Format Flexibility**: Accepts various datetime formats
- **Future Planning**: Default dates set for tomorrow through next month

### Prerequisites

Before testing onsite branches, ensure you have:
1. At least one active Branch in the system
2. At least one active AppointmentCorporateCode 
3. Proper database connectivity

### Error Handling

The tester includes comprehensive error handling for:

- Database connection failures
- API server connectivity issues
- Invalid responses
- Invalid branch or corporate code IDs
- Date range validation errors
- Timezone conversion issues
- Missing dependencies
- User interruption (Ctrl+C)

### Dependencies

- **typer**: Modern CLI framework
- **rich**: Beautiful terminal formatting
- **fastapi.testclient**: For API testing
- **sqlalchemy**: Database ORM for verification

### Integration

This module imports directly from the parent backend-patient-app modules:
- Database models (`AppointmentOnsiteBranch`, `AppointmentCorporateCode`, `Branch`)
- Session management (`SessionLocal`)
- FastAPI app (`main.app`)

### Filtering Examples

The tester supports various filtering scenarios:

```bash
# Test filtering by corporate code
uv run cli/onsite_branch_tester.py list-only --corporate-code-id "123e4567-e89b-12d3-a456-426614174000"

# Test filtering by branch
uv run cli/onsite_branch_tester.py list-only --branch-id "987fcdeb-51a2-43d1-b789-123456789abc"

# Combined filtering is also supported by the API
```

Make sure the backend application is properly configured with database access before running tests.