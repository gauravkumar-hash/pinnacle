#!/usr/bin/env python3
"""
CLI AppointmentCorporateCode CRUD Tester

This CLI application allows testing the AppointmentCorporateCode CRUD operations by:
1. Accepting user input for Corporate Code data
2. Making API calls to test CRUD operations
3. Verifying database records are saved correctly

Usage:
    uv run cli/corporate_code_tester.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

# Add parent directory to Python path to import from backend-patient-app
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from models.appointment import AppointmentCorporateCode, AppointmentServiceGroup, AppointmentOnsiteBranch
    from models.pinnacle import Branch
    from models import SessionLocal
except ImportError as e:
    console = Console()
    console.print(f"[red]Error importing dependencies: {e}[/red]")
    console.print("[yellow]Make sure you have the dev dependencies installed: uv sync --dev[/yellow]")
    console.print(f"[yellow]Current working directory: {Path.cwd()}[/yellow]")
    console.print(f"[yellow]Script location: {Path(__file__).parent}[/yellow]")
    console.print(f"[yellow]Parent directory added to path: {parent_dir}[/yellow]")
    raise typer.Exit(1)

# Initialize rich console for beautiful CLI output
console = Console()
app = typer.Typer(help="CLI AppointmentCorporateCode CRUD Tester")

from fastapi.testclient import TestClient
from routers.admin.utils import get_current_user
from main import app as fastapi_app

def override_get_current_user():
    return {"user_id": '123'}

fastapi_app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(fastapi_app)

class CorporateCodeTester:
    def __init__(self, base_url: str = "/api/admin/appointments/v1"):
        self.base_url = base_url
        self.created_corporate_codes: List[str] = []  # Track created IDs for cleanup

    async def test_create_corporate_code(self, corporate_code_data: Dict[str, Any]) -> Optional[str]:
        """Test creating a corporate code via API"""
        console.print("\n[bold blue]Testing CREATE Corporate Code API[/bold blue]")
        
        try:
            response = client.post(
                f"{self.base_url}/corporate-codes",
                json=corporate_code_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                corporate_code_id = result.get("id")
                console.print(f"✅ [green]CREATE API Success: ID {corporate_code_id}[/green]")
                
                if corporate_code_id:
                    self.created_corporate_codes.append(corporate_code_id)
                
                return corporate_code_id
            else:
                console.print(f"❌ [red]CREATE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]CREATE API Error: {e}[/red]")
            return None
    
    async def test_get_corporate_code(self, corporate_code_id: str) -> Optional[Dict[str, Any]]:
        """Test getting a specific corporate code via API"""
        console.print(f"\n[bold blue]Testing GET Corporate Code API (ID: {corporate_code_id})[/bold blue]")
        
        try:
            response = client.get(
                f"{self.base_url}/corporate-codes/{corporate_code_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print("✅ [green]GET API Success[/green]")
                
                # Display corporate code details
                table = Table(title="Corporate Code Details")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")
                
                for key, value in result.items():
                    if isinstance(value, dict) or isinstance(value, list):
                        table.add_row(str(key), str(value)[:100] + "..." if len(str(value)) > 100 else str(value))
                    else:
                        table.add_row(str(key), str(value))
                
                console.print(table)
                return result
            else:
                console.print(f"❌ [red]GET API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]GET API Error: {e}[/red]")
            return None
    
    async def test_update_corporate_code(self, corporate_code_id: str, update_data: Dict[str, Any]) -> bool:
        """Test updating a corporate code via API"""
        console.print(f"\n[bold blue]Testing UPDATE Corporate Code API (ID: {corporate_code_id})[/bold blue]")
        
        try:
            response = client.put(
                f"{self.base_url}/corporate-codes/{corporate_code_id}",
                json=update_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                console.print("✅ [green]UPDATE API Success[/green]")
                return True
            else:
                console.print(f"❌ [red]UPDATE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            console.print(f"❌ [red]UPDATE API Error: {e}[/red]")
            return False

    async def test_list_corporate_codes(self) -> Optional[List[Dict[str, Any]]]:
        """Test listing all corporate codes via API"""
        console.print("\n[bold blue]Testing LIST Corporate Codes API[/bold blue]")
        
        try:
            response = client.get(
                f"{self.base_url}/corporate-codes",
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print(f"✅ [green]LIST API Success: Found {len(result)} corporate codes[/green]")
                
                # Display list in table format
                if result:
                    table = Table(title="All Corporate Codes")
                    table.add_column("ID", style="cyan", no_wrap=True)
                    table.add_column("Code", style="magenta")
                    table.add_column("Organization", style="yellow")
                    table.add_column("Active", style="green")
                    table.add_column("Valid From", style="blue")
                    table.add_column("Valid To", style="blue")
                    
                    for code in result:
                        table.add_row(
                            str(code.get("id", ""))[:8] + "...",
                            str(code.get("code", "")),
                            str(code.get("organization", "")),
                            "✅" if code.get("is_active", False) else "❌",
                            str(code.get("valid_from", "None")),
                            str(code.get("valid_to", "None"))
                        )
                    
                    console.print(table)
                
                return result
            else:
                console.print(f"❌ [red]LIST API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]LIST API Error: {e}[/red]")
            return None
    
    async def test_delete_corporate_code(self, corporate_code_id: str) -> bool:
        """Test deleting a corporate code via API"""
        console.print(f"\n[bold blue]Testing DELETE Corporate Code API (ID: {corporate_code_id})[/bold blue]")
        
        try:
            response = client.delete(
                f"{self.base_url}/corporate-codes/{corporate_code_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                console.print("✅ [green]DELETE API Success[/green]")
                if corporate_code_id in self.created_corporate_codes:
                    self.created_corporate_codes.remove(corporate_code_id)
                return True
            else:
                console.print(f"❌ [red]DELETE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            console.print(f"❌ [red]DELETE API Error: {e}[/red]")
            return False

    def verify_database_record(self, corporate_code_id: str, expected_data: Dict[str, Any]) -> bool:
        """Verify that the corporate code record exists and matches expected data in database"""
        console.print(f"\n[bold blue]Verifying Database Record (ID: {corporate_code_id})[/bold blue]")
        
        try:
            with SessionLocal() as db:
                corporate_code = db.query(AppointmentCorporateCode).filter(
                    AppointmentCorporateCode.id == corporate_code_id
                ).first()
                
                if not corporate_code:
                    console.print("❌ [red]Database Verification Failed: Record not found[/red]")
                    return False
                
                console.print("✅ [green]Database Record Found[/green]")
                
                # Verify specific fields
                verification_results = []
                
                if "code" in expected_data:
                    matches = corporate_code.code == expected_data["code"]
                    verification_results.append(("code", corporate_code.code, expected_data["code"], matches))
                
                if "organization" in expected_data:
                    matches = corporate_code.organization == expected_data["organization"]
                    verification_results.append(("organization", corporate_code.organization, expected_data["organization"], matches))
                
                if "is_active" in expected_data:
                    matches = corporate_code.is_active == expected_data["is_active"]
                    verification_results.append(("is_active", corporate_code.is_active, expected_data["is_active"], matches))
                
                if "valid_from" in expected_data:
                    # Handle None/datetime comparison
                    db_val = corporate_code.valid_from.isoformat() if corporate_code.valid_from else None
                    exp_val = expected_data["valid_from"]
                    matches = db_val == exp_val
                    verification_results.append(("valid_from", db_val, exp_val, matches))
                
                if "valid_to" in expected_data:
                    # Handle None/datetime comparison
                    db_val = corporate_code.valid_to.isoformat() if corporate_code.valid_to else None
                    exp_val = expected_data["valid_to"]
                    matches = db_val == exp_val
                    verification_results.append(("valid_to", db_val, exp_val, matches))
                
                # Display verification results
                table = Table(title="Database Verification Results")
                table.add_column("Field", style="cyan")
                table.add_column("DB Value", style="yellow")
                table.add_column("Expected", style="yellow")
                table.add_column("Match", style="green")
                
                all_matches = True
                for field, db_value, expected_value, matches in verification_results:
                    status = "✅" if matches else "❌"
                    table.add_row(field, str(db_value), str(expected_value), status)
                    if not matches:
                        all_matches = False
                
                console.print(table)
                
                if all_matches:
                    console.print("✅ [green]All database fields match expected values[/green]")
                else:
                    console.print("❌ [red]Some database fields don't match expected values[/red]")
                
                return all_matches
                
        except Exception as e:
            console.print(f"❌ [red]Database Verification Error: {e}[/red]")
            return False
    
    def verify_record_deleted(self, corporate_code_id: str) -> bool:
        """Verify that a corporate code record has been deleted from the database"""
        console.print(f"\n[bold blue]Verifying record deletion from database[/bold blue]")
        try:
            with SessionLocal() as db:
                corporate_code = db.query(AppointmentCorporateCode).filter(
                    AppointmentCorporateCode.id == corporate_code_id
                ).first()
                
                if corporate_code is None:
                    console.print("✅ [green]Record successfully deleted from database[/green]")
                    return True
                else:
                    console.print("❌ [red]Record still exists in database[/red]")
                    return False
        except Exception as e:
            console.print(f"❌ [red]Error checking deletion: {e}[/red]")
            return False
    
    async def cleanup_created_records(self):
        """Clean up any corporate codes created during testing"""
        if not self.created_corporate_codes:
            return
            
        console.print(f"\n[bold yellow]Cleaning up {len(self.created_corporate_codes)} created corporate codes[/bold yellow]")
        
        for corporate_code_id in self.created_corporate_codes.copy():
            await self.test_delete_corporate_code(corporate_code_id)

def get_available_service_groups() -> List[Dict[str, str]]:
    """Get available service groups from database"""
    try:
        with SessionLocal() as db:
            service_groups = db.query(AppointmentServiceGroup).order_by(AppointmentServiceGroup.index).all()
            return [{
                "id": str(sg.id), 
                "name": sg.name,
                "type": sg.type.value if sg.type else "unknown"
            } for sg in service_groups]
    except Exception as e:
        console.print(f"[red]Error fetching service groups: {e}[/red]")
        return []

def get_available_branches() -> List[Dict[str, str]]:
    """Get available branches from database"""
    try:
        with SessionLocal() as db:
            branches = db.query(Branch).filter(
                Branch.deleted == False,
                Branch.hidden == False
            ).order_by(Branch.name).all()
            return [{
                "id": str(branch.id), 
                "name": branch.name, 
                "sgimed_branch_id": branch.sgimed_branch_id
            } for branch in branches]
    except Exception as e:
        console.print(f"[red]Error fetching branches: {e}[/red]")
        return []

def get_user_input() -> Dict[str, Any]:
    """Get corporate code data from user input"""
    console.print("\n[bold green]Enter Corporate Code Information[/bold green]")
    
    code = Prompt.ask("Corporate Code", default="TEST-CORP-001")
    organization = Prompt.ask("Organization Name", default="Test Organization Ltd")
    is_active = Confirm.ask("Is Active?", default=True)
    
    # Validity period
    add_validity = Confirm.ask("Add validity period?", default=False)
    valid_from = None
    valid_to = None
    
    if add_validity:
        valid_from_str = Prompt.ask("Valid From (YYYY-MM-DD HH:MM:SS or Enter for now)", default="")
        if valid_from_str:
            try:
                valid_from = datetime.fromisoformat(valid_from_str).isoformat()
            except ValueError:
                console.print("[yellow]Invalid date format, using current time[/yellow]")
                valid_from = datetime.now().isoformat()
        else:
            valid_from = datetime.now().isoformat()
            
        valid_to_str = Prompt.ask("Valid To (YYYY-MM-DD HH:MM:SS or Enter for none)", default="")
        if valid_to_str:
            try:
                valid_to = datetime.fromisoformat(valid_to_str).isoformat()
            except ValueError:
                console.print("[yellow]Invalid date format, leaving valid_to as None[/yellow]")
    
    # Survey configurations
    patient_survey = {}
    corporate_survey = {}
    
    # Basic survey structure for testing
    add_surveys = Confirm.ask("Add sample survey questions?", default=True)
    if add_surveys:
        patient_survey = {
            "questions": [
                {"id": "name", "type": "text", "label": "Patient Name", "required": True},
                {"id": "nric", "type": "text", "label": "NRIC/FIN", "required": True},
                {"id": "department", "type": "select", "label": "Department", "options": ["HR", "IT", "Finance"], "required": False}
            ]
        }
        corporate_survey = {
            "questions": [
                {"id": "employee_id", "type": "text", "label": "Employee ID", "required": True},
                {"id": "cost_center", "type": "text", "label": "Cost Center", "required": False}
            ]
        }
    
    # Service Group selection (optional)
    service_group_ids = []
    add_service_groups = Confirm.ask("Link to service groups?", default=False)
    if add_service_groups:
        service_groups = get_available_service_groups()
        if service_groups:
            console.print("\nAvailable Service Groups:")
            for i, sg in enumerate(service_groups, 1):
                console.print(f"{i}. {sg['name']} ({sg['type']}) - ID: {sg['id'][:8]}...")
            
            selection = Prompt.ask("Choose service groups (e.g., 1,3,5) or Enter for none", default="")
            if selection.strip():
                try:
                    selected_indices = [int(x.strip()) - 1 for x in selection.split(",")]
                    for idx in selected_indices:
                        if 0 <= idx < len(service_groups):
                            service_group_ids.append(service_groups[idx]["id"])
                    console.print(f"Selected service groups: {len(service_group_ids)} groups")
                except (ValueError, IndexError):
                    console.print("[yellow]Invalid selection, skipping service groups[/yellow]")
        else:
            console.print("[yellow]No service groups found in database[/yellow]")
    
    return {
        "code": code,
        "organization": organization,
        "patient_survey": patient_survey,
        "corporate_survey": corporate_survey,
        "valid_from": valid_from,
        "valid_to": valid_to,
        "is_active": is_active,
        "service_group_ids": service_group_ids
    }

def get_update_data() -> Dict[str, Any]:
    """Get update data from user"""
    console.print("\n[bold green]Enter fields to update (leave empty to skip)[/bold green]")
    
    update_data = {}
    
    code = Prompt.ask("New code (or press Enter to skip)", default="")
    if code:
        update_data["code"] = code
    
    organization = Prompt.ask("New organization (or press Enter to skip)", default="")
    if organization:
        update_data["organization"] = organization
    
    is_active = Prompt.ask("New active status (true/false or press Enter to skip)", default="")
    if is_active.lower() in ["true", "false"]:
        update_data["is_active"] = is_active.lower() == "true"
    
    valid_from = Prompt.ask("New valid_from (YYYY-MM-DD HH:MM:SS or press Enter to skip)", default="")
    if valid_from:
        try:
            update_data["valid_from"] = datetime.fromisoformat(valid_from).isoformat()
        except ValueError:
            console.print("[yellow]Invalid date format, skipping valid_from[/yellow]")
    
    valid_to = Prompt.ask("New valid_to (YYYY-MM-DD HH:MM:SS or press Enter to skip)", default="")
    if valid_to:
        try:
            update_data["valid_to"] = datetime.fromisoformat(valid_to).isoformat()
        except ValueError:
            console.print("[yellow]Invalid date format, skipping valid_to[/yellow]")
    
    return update_data

def show_edge_cases():
    """Display edge cases that should be tested"""
    console.print("\n[bold yellow]🔍 IMPORTANT EDGE CASES TO TEST[/bold yellow]")
    console.print("\n[bold cyan]🏢 Corporate Code Validation:[/bold cyan]")
    console.print("• ✅ Unique corporate codes - Should succeed")
    console.print("• ❌ Duplicate corporate codes - Should FAIL")
    console.print("• 🔍 Case sensitivity testing (TEST vs test vs Test)")
    console.print("• 🔍 Special characters in codes (@, #, -, _)")
    console.print("• 🔍 Very long corporate codes (100+ characters)")
    console.print("• ❌ Empty/null corporate codes - Should fail")
    
    console.print("\n[bold cyan]🏭 Organization Validation:[/bold cyan]")
    console.print("• ✅ Normal organization names")
    console.print("• 🔍 Very long organization names (255+ characters)")
    console.print("• 🔍 Special characters in organization names")
    console.print("• ❌ Empty organization names - Should fail")
    console.print("• 🔍 Unicode characters in organization names")
    
    console.print("\n[bold cyan]📅 Validity Period Testing:[/bold cyan]")
    console.print("• ✅ No validity period (always valid)")
    console.print("• ✅ Future validity period")
    console.print("• ✅ Current validity period")
    console.print("• ❌ Past validity period - Should be handled properly")
    console.print("• ❌ valid_to before valid_from - Should FAIL")
    console.print("• 🔍 Timezone handling in datetime fields")
    
    console.print("\n[bold cyan]📊 Survey Configuration:[/bold cyan]")
    console.print("• ✅ Valid JSON survey structures")
    console.print("• ❌ Invalid JSON in survey fields - Should fail")
    console.print("• 🔍 Empty survey objects vs null")
    console.print("• 🔍 Very large survey configurations")
    console.print("• 🔍 Survey questions with all field types")
    
    console.print("\n[bold cyan]🔗 Service Group Relationships:[/bold cyan]")
    console.print("• ✅ No linked service groups")
    console.print("• ✅ Valid service group linkages")
    console.print("• ❌ Invalid/non-existent service group IDs - Should fail")
    console.print("• 🔍 Linking to all available service groups")
    console.print("• 🔍 Service group deletion when linked to corporate codes")
    
    console.print("\n[bold cyan]🏪 Onsite Branch Management:[/bold cyan]")
    console.print("• ✅ No onsite branches")
    console.print("• ✅ Valid onsite branch configurations")
    console.print("• ❌ Invalid branch IDs - Should fail")
    console.print("• 🔍 Overlapping date ranges for same branch")
    console.print("• 🔍 Past/future onsite branch dates")
    
    console.print("\n[bold cyan]🔄 Update Operations:[/bold cyan]")
    console.print("• ✅ Update individual fields")
    console.print("• ✅ Update multiple fields at once")
    console.print("• ❌ Update to duplicate code - Should fail")
    console.print("• 🔍 Update surveys while preserving structure")
    console.print("• 🔍 Update service group linkages")
    console.print("• 🔍 Partial updates should preserve existing values")
    
    console.print("\n[bold cyan]🗑️ Delete Operations:[/bold cyan]")
    console.print("• ❌ Delete corporate code with existing appointments - Should FAIL")
    console.print("• ✅ Delete corporate code with no appointments - Should succeed")
    console.print("• ❌ Delete non-existent corporate code - Should return 404")
    console.print("• ❌ Delete same corporate code twice - Should fail gracefully")
    console.print("• 🔍 Verify linked service groups are unlinked after deletion")
    
    console.print("\n[bold cyan]🔍 API Validation:[/bold cyan]")
    console.print("• 🔍 Validate corporate code endpoint (patient API)")
    console.print("• 🔍 Patient survey retrieval")
    console.print("• 🔍 Corporate survey retrieval")
    console.print("• ❌ Access with invalid/expired codes")
    
    console.print("\n[bold red]💡 Testing Tips:[/bold red]")
    console.print("• Use 'verify-db <id>' after each operation to check database state")
    console.print("• Test both happy paths (✅) and expected failures (❌)")
    console.print("• Pay attention to survey JSON structure validation")
    console.print("• Test validity period logic with different date scenarios")
    console.print("• Check API responses AND database consistency")
    console.print("• Verify related entities (service groups, onsite branches) are properly managed")

@app.command()
def edge_cases():
    """Display comprehensive edge cases and testing scenarios for Corporate Codes"""
    show_edge_cases()

@app.command()
def test_crud(
    base_url: Annotated[str, typer.Option(help="Base URL of the API server")] = "/api/admin/appointments/v1",
    auto_cleanup: Annotated[bool, typer.Option("--auto-cleanup/--no-auto-cleanup", help="Automatically cleanup created records")] = True,
    show_edge_cases_flag: Annotated[bool, typer.Option("--show-edge-cases", help="Display edge cases before testing")] = True
):
    """Run the complete Corporate Code CRUD test suite"""
    
    console.print(Panel.fit(
        "[bold blue]Corporate Code CRUD Tester[/bold blue]\n"
        "This tool tests the AppointmentCorporateCode CRUD operations via API calls\n"
        "and verifies database records are saved correctly.\n\n"
        "[yellow]💡 Use --show-edge-cases to see important test scenarios[/yellow]",
        border_style="blue"
    ))
    
    if show_edge_cases_flag:
        show_edge_cases()
        if not Confirm.ask("\n[bold]Continue with testing?[/bold]", default=True):
            raise typer.Exit(0)
    
    try:
        tester = CorporateCodeTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_tests():
        try:
            # Test 1: Create Corporate Code
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 1: CREATE CORPORATE CODE[/bold cyan]")
            console.print("="*60)
            
            corporate_code_data = get_user_input()
            corporate_code_id = await tester.test_create_corporate_code(corporate_code_data)
            
            if not corporate_code_id:
                console.print("❌ [red]CREATE test failed, stopping here[/red]")
                return
            
            # Verify database record after creation
            tester.verify_database_record(corporate_code_id, corporate_code_data)
            
            # Test 2: Get Corporate Code
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 2: GET CORPORATE CODE[/bold cyan]")
            console.print("="*60)
            
            await tester.test_get_corporate_code(corporate_code_id)
            
            # Test 3: List All Corporate Codes
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 3: LIST ALL CORPORATE CODES[/bold cyan]")
            console.print("="*60)
            
            await tester.test_list_corporate_codes()
            
            # Test 4: Update Corporate Code
            if Confirm.ask("\nDo you want to test UPDATE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 4: UPDATE CORPORATE CODE[/bold cyan]")
                console.print("="*60)
                
                update_data = get_update_data()
                if update_data:
                    success = await tester.test_update_corporate_code(corporate_code_id, update_data)
                    if success:
                        # Verify database record after update
                        combined_data = {**corporate_code_data, **update_data}
                        tester.verify_database_record(corporate_code_id, combined_data)
                        
                        # Get updated record via API
                        await tester.test_get_corporate_code(corporate_code_id)
            
            # Test 5: Delete Corporate Code
            if Confirm.ask("\nDo you want to test DELETE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 5: DELETE CORPORATE CODE[/bold cyan]")
                console.print("="*60)
                
                delete_success = await tester.test_delete_corporate_code(corporate_code_id)
                
                if delete_success:
                    # Verify record is deleted from database
                    tester.verify_record_deleted(corporate_code_id)
            
            # Summary
            console.print("\n" + "="*60)
            console.print("[bold green]TESTING COMPLETE[/bold green]")
            console.print("="*60)
            console.print("All CRUD operations have been tested.")
            console.print("Check the output above for any failures or issues.")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]Testing interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"\n❌ [red]Unexpected error: {e}[/red]")
        finally:
            # Cleanup
            if auto_cleanup:
                await tester.cleanup_created_records()
    
    # Run the async tests
    asyncio.run(run_tests())

@app.command()
def list_only(
    base_url: Annotated[str, typer.Option(help="Base URL of the API server")] = "/api/admin/appointments/v1"
):
    """Only test the LIST operation to see existing corporate codes"""
    
    console.print("[bold blue]Listing all corporate codes...[/bold blue]")
    
    try:
        tester = CorporateCodeTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_list():
        await tester.test_list_corporate_codes()
    
    asyncio.run(run_list())

@app.command()
def verify_db(
    corporate_code_id: Annotated[str, typer.Argument(help="Corporate Code ID to verify in database")]
):
    """Verify a specific corporate code exists in the database"""
    
    console.print(f"[bold blue]Verifying corporate code {corporate_code_id} in database...[/bold blue]")
    
    try:
        with SessionLocal() as db:
            corporate_code = db.query(AppointmentCorporateCode).filter(
                AppointmentCorporateCode.id == corporate_code_id
            ).first()
            
            if not corporate_code:
                console.print("❌ [red]Corporate code not found in database[/red]")
                raise typer.Exit(1)
            
            console.print("✅ [green]Corporate code found in database[/green]")
            
            # Display details
            table = Table(title="Database Record Details")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("ID", str(corporate_code.id))
            table.add_row("Code", str(corporate_code.code))
            table.add_row("Organization", str(corporate_code.organization))
            table.add_row("Is Active", str(corporate_code.is_active))
            table.add_row("Valid From", str(corporate_code.valid_from or "None"))
            table.add_row("Valid To", str(corporate_code.valid_to or "None"))
            table.add_row("Patient Survey", str(corporate_code.patient_survey)[:100] + "..." if len(str(corporate_code.patient_survey)) > 100 else str(corporate_code.patient_survey))
            table.add_row("Corporate Survey", str(corporate_code.corporate_survey)[:100] + "..." if len(str(corporate_code.corporate_survey)) > 100 else str(corporate_code.corporate_survey))
            table.add_row("Created At", str(corporate_code.created_at))
            table.add_row("Updated At", str(corporate_code.updated_at))
            
            console.print(table)
            
            # Show related service groups
            if corporate_code.appointment_service_groups:
                console.print(f"\n[bold cyan]Linked Service Groups ({len(corporate_code.appointment_service_groups)}):[/bold cyan]")
                sg_table = Table()
                sg_table.add_column("ID", style="cyan")
                sg_table.add_column("Name", style="magenta")
                sg_table.add_column("Type", style="yellow")
                
                for sg in corporate_code.appointment_service_groups:
                    sg_table.add_row(str(sg.id)[:8] + "...", sg.name, sg.type.value if sg.type else "unknown")
                
                console.print(sg_table)
            else:
                console.print("\n[yellow]No linked service groups[/yellow]")
            
            # Show related onsite branches
            if corporate_code.appointment_onsite_branches:
                console.print(f"\n[bold cyan]Onsite Branches ({len(corporate_code.appointment_onsite_branches)}):[/bold cyan]")
                branch_table = Table()
                branch_table.add_column("ID", style="cyan")
                branch_table.add_column("Header", style="magenta")
                branch_table.add_column("Start Date", style="green")
                branch_table.add_column("End Date", style="red")
                
                for branch in corporate_code.appointment_onsite_branches:
                    branch_table.add_row(
                        str(branch.id),
                        str(branch.header or "None"),
                        str(branch.start_date),
                        str(branch.end_date)
                    )
                
                console.print(branch_table)
            else:
                console.print("\n[yellow]No onsite branches[/yellow]")
            
    except Exception as e:
        console.print(f"[red]Database verification error: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()