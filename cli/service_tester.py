#!/usr/bin/env python3
"""
CLI Service CRUD Tester

This CLI application allows testing the Service CRUD operations by:
1. Accepting user input for Service data
2. Making API calls to test CRUD operations
3. Verifying database records are saved correctly

Usage:
    uv run cli/service_tester.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any, Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

# Add parent directory to Python path to import from backend-patient-app
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

try:
    from models.appointment import AppointmentService, AppointmentServiceGroup
    from models.sgimed import SGiMedInventory
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
app = typer.Typer(help="CLI Service CRUD Tester")

from fastapi.testclient import TestClient
from routers.admin.utils import get_current_user
from main import app as fastapi_app

def override_get_current_user():
    return {"user_id": '123'}

fastapi_app.dependency_overrides[get_current_user] = override_get_current_user
client = TestClient(fastapi_app)

class ServiceTester:
    def __init__(self, base_url: str = "/api/admin/appointments/v1"):
        self.base_url = base_url
        self.created_services: List[str] = []  # Track created IDs for cleanup

    async def test_create_service(self, service_data: Dict[str, Any]) -> Optional[str]:
        """Test creating a service via API"""
        console.print("\n[bold blue]Testing CREATE Service API[/bold blue]")
        
        try:
            response = client.post(
                f"{self.base_url}/services",
                json=service_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                service_id = result.get("id")
                console.print(f"✅ [green]CREATE API Success: ID {service_id}[/green]")
                
                if service_id:
                    self.created_services.append(service_id)
                
                return service_id
            else:
                console.print(f"❌ [red]CREATE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]CREATE API Error: {e}[/red]")
            return None
    
    async def test_get_service(self, service_id: str) -> Optional[Dict[str, Any]]:
        """Test getting a specific service via API"""
        console.print(f"\n[bold blue]Testing GET Service API (ID: {service_id})[/bold blue]")
        
        try:
            response = client.get(
                f"{self.base_url}/services/{service_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print("✅ [green]GET API Success[/green]")
                
                # Display service details
                table = Table(title="Service Details")
                table.add_column("Field", style="cyan")
                table.add_column("Value", style="magenta")
                
                for key, value in result.items():
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
    
    async def test_update_service(self, service_id: str, update_data: Dict[str, Any]) -> bool:
        """Test updating a service via API"""
        console.print(f"\n[bold blue]Testing UPDATE Service API (ID: {service_id})[/bold blue]")
        
        try:
            response = client.put(
                f"{self.base_url}/services/{service_id}",
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

    async def test_list_services(self, group_id: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """Test listing all services via API"""
        console.print("\n[bold blue]Testing LIST Services API[/bold blue]")
        
        try:
            params = {}
            if group_id:
                params["group_id"] = group_id
                
            response = client.get(
                f"{self.base_url}/services",
                params=params,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print(f"✅ [green]LIST API Success: Found {len(result)} services[/green]")
                
                # Display list in table format
                if result:
                    table = Table(title="All Services")
                    table.add_column("ID", style="cyan", no_wrap=True)
                    table.add_column("Name", style="magenta")
                    table.add_column("Group", style="yellow")
                    table.add_column("Prepayment", style="green")
                    table.add_column("Display", style="blue")
                    table.add_column("Index", style="red")
                    
                    for service in result:
                        table.add_row(
                            str(service.get("id", ""))[:8] + "...",
                            str(service.get("name", "")),
                            str(service.get("group_name", "")),
                            f"${service.get('prepayment_price', 0):.2f}",
                            f"${service.get('display_price', 0):.2f}",
                            str(service.get("index", ""))
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
    
    async def test_delete_service(self, service_id: str) -> bool:
        """Test deleting a service via API"""
        console.print(f"\n[bold blue]Testing DELETE Service API (ID: {service_id})[/bold blue]")
        
        try:
            response = client.delete(
                f"{self.base_url}/services/{service_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                console.print("✅ [green]DELETE API Success[/green]")
                if service_id in self.created_services:
                    self.created_services.remove(service_id)
                return True
            else:
                console.print(f"❌ [red]DELETE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            console.print(f"❌ [red]DELETE API Error: {e}[/red]")
            return False

    def verify_database_record(self, service_id: str, expected_data: Dict[str, Any]) -> bool:
        """Verify that the service record exists and matches expected data in database"""
        console.print(f"\n[bold blue]Verifying Database Record (ID: {service_id})[/bold blue]")
        
        try:
            with SessionLocal() as db:
                service = db.query(AppointmentService).filter(
                    AppointmentService.id == service_id
                ).first()
                
                if not service:
                    console.print("❌ [red]Database Verification Failed: Record not found[/red]")
                    return False
                
                console.print("✅ [green]Database Record Found[/green]")
                
                # Verify specific fields
                verification_results = []
                
                if "name" in expected_data:
                    matches = service.name == expected_data["name"]
                    verification_results.append(("name", service.name, expected_data["name"], matches))
                
                if "prepayment_price" in expected_data:
                    matches = float(service.prepayment_price) == float(expected_data["prepayment_price"])
                    verification_results.append(("prepayment_price", service.prepayment_price, expected_data["prepayment_price"], matches))
                
                if "display_price" in expected_data:
                    matches = float(service.display_price) == float(expected_data["display_price"])
                    verification_results.append(("display_price", service.display_price, expected_data["display_price"], matches))
                
                if "index" in expected_data:
                    matches = service.index == expected_data["index"]
                    verification_results.append(("index", service.index, expected_data["index"], matches))
                
                if "min_booking_ahead_days" in expected_data:
                    matches = service.min_booking_ahead_days == expected_data["min_booking_ahead_days"]
                    verification_results.append(("min_booking_ahead_days", service.min_booking_ahead_days, expected_data["min_booking_ahead_days"], matches))
                
                if "sgimed_inventory_id" in expected_data:
                    matches = service.sgimed_inventory_id == expected_data["sgimed_inventory_id"]
                    verification_results.append(("sgimed_inventory_id", service.sgimed_inventory_id, expected_data["sgimed_inventory_id"], matches))
                
                if "restricted_branches" in expected_data:
                    matches = service.restricted_branches == expected_data["restricted_branches"]
                    verification_results.append(("restricted_branches", service.restricted_branches, expected_data["restricted_branches"], matches))
                
                if "group_id" in expected_data:
                    matches = str(service.group_id) == str(expected_data["group_id"])
                    verification_results.append(("group_id", str(service.group_id), str(expected_data["group_id"]), matches))
                
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
    
    def verify_record_deleted(self, service_id: str) -> bool:
        """Verify that a service record has been deleted from the database"""
        console.print(f"\n[bold blue]Verifying record deletion from database[/bold blue]")
        try:
            with SessionLocal() as db:
                service = db.query(AppointmentService).filter(
                    AppointmentService.id == service_id
                ).first()
                
                if service is None:
                    console.print("✅ [green]Record successfully deleted from database[/green]")
                    return True
                else:
                    console.print("❌ [red]Record still exists in database[/red]")
                    return False
        except Exception as e:
            console.print(f"❌ [red]Error checking deletion: {e}[/red]")
            return False
    
    async def cleanup_created_records(self):
        """Clean up any services created during testing"""
        if not self.created_services:
            return
            
        console.print(f"\n[bold yellow]Cleaning up {len(self.created_services)} created services[/bold yellow]")
        
        for service_id in self.created_services.copy():
            await self.test_delete_service(service_id)

def get_available_service_groups() -> List[Dict[str, str]]:
    """Get available service groups from database"""
    try:
        with SessionLocal() as db:
            service_groups = db.query(AppointmentServiceGroup).order_by(AppointmentServiceGroup.index).all()
            return [{"id": str(sg.id), "name": sg.name} for sg in service_groups]
    except Exception as e:
        console.print(f"[red]Error fetching service groups: {e}[/red]")
        return []

def get_available_inventories() -> List[Dict[str, str]]:
    """Get available SGiMed inventories from database"""
    try:
        with SessionLocal() as db:
            # Note: SGiMedInventory doesn't have is_enabled field, so we get all inventories
            inventories = db.query(SGiMedInventory).order_by(SGiMedInventory.name).limit(20).all()
            return [{"id": inventory.id, "name": inventory.name} for inventory in inventories]
    except Exception as e:
        console.print(f"[red]Error fetching inventories: {e}[/red]")
        return []

def get_available_branches() -> List[Dict[str, str]]:
    """Get available branches from database"""
    try:
        with SessionLocal() as db:
            branches = db.query(Branch).filter(
                Branch.deleted == False
            ).order_by(Branch.name).all()
            return [{"id": str(branch.id), "name": branch.name, "sgimed_branch_id": branch.sgimed_branch_id} for branch in branches]
    except Exception as e:
        console.print(f"[red]Error fetching branches: {e}[/red]")
        return []

def get_user_input() -> Dict[str, Any]:
    """Get service data from user input"""
    console.print("\n[bold green]Enter Service Information[/bold green]")
    
    name = Prompt.ask("Service Name", default="Test Service")
    prepayment_price = float(Prompt.ask("Prepayment Price", default="0.0"))
    display_price = float(Prompt.ask("Display Price", default="50.0"))
    index = int(Prompt.ask("Index (sorting order)", default="1"))
    min_booking_ahead_days = int(Prompt.ask("Min booking ahead days", default="2"))
    
    # Service Group selection
    service_groups = get_available_service_groups()
    if not service_groups:
        console.print("[red]No service groups found! Create a service group first.[/red]")
        raise typer.Exit(1)
    
    console.print("\nAvailable Service Groups:")
    for i, sg in enumerate(service_groups, 1):
        console.print(f"{i}. {sg['name']} (ID: {sg['id'][:8]}...)")
    
    group_choice = int(Prompt.ask("Choose service group", choices=[str(i) for i in range(1, len(service_groups) + 1)], default="1"))
    selected_group = service_groups[group_choice - 1]
    
    # SGiMed Inventory (optional)
    sgimed_inventory_id = None
    if prepayment_price > 0 or Confirm.ask("Link to SGiMed inventory?", default=False):
        inventories = get_available_inventories()
        if inventories:
            console.print("\nAvailable SGiMed Inventories:")
            console.print("0. None")
            for i, inv in enumerate(inventories, 1):
                console.print(f"{i}. {inv['name']} (ID: {inv['id']})")
            
            inv_choices = ["0"] + [str(i) for i in range(1, len(inventories) + 1)]
            inv_choice = int(Prompt.ask("Choose inventory", choices=inv_choices, default="0"))
            
            if inv_choice > 0:
                sgimed_inventory_id = inventories[inv_choice - 1]["id"]
    
    # Restricted branches (optional)
    add_branches = Confirm.ask("Add restricted branches?", default=False)
    restricted_branches = []
    if add_branches:
        branches = get_available_branches()
        if branches:
            console.print("\nAvailable Branches:")
            console.print("Select branches (enter numbers separated by commas, or press Enter for none):")
            for i, branch in enumerate(branches, 1):
                console.print(f"{i}. {branch['name']} (ID: {branch['sgimed_branch_id']})")
            
            branch_selection = Prompt.ask("Choose branches (e.g., 1,3,5)", default="")
            if branch_selection.strip():
                try:
                    selected_indices = [int(x.strip()) - 1 for x in branch_selection.split(",")]
                    for idx in selected_indices:
                        if 0 <= idx < len(branches):
                            restricted_branches.append(branches[idx]["id"])
                    console.print(f"Selected branches: {restricted_branches}")
                except (ValueError, IndexError):
                    console.print("[yellow]Invalid selection, skipping branch restrictions[/yellow]")
        else:
            console.print("[yellow]No branches found in database[/yellow]")
    
    # Tests (optional)
    tests = None
    if Confirm.ask("Add test items?", default=False):
        tests = []
        while True:
            test_name = Prompt.ask("Test name (or Enter to finish)", default="")
            if not test_name:
                break
            test_exclusion = Prompt.ask("Test exclusion", default="")
            tests.append({"name": test_name, "exclusion": test_exclusion})
    
    return {
        "name": name,
        "prepayment_price": prepayment_price,
        "display_price": display_price,
        "index": index,
        "min_booking_ahead_days": min_booking_ahead_days,
        "sgimed_inventory_id": sgimed_inventory_id,
        "restricted_branches": restricted_branches,
        "tests": tests,
        "group_id": selected_group["id"]
    }

def get_update_data() -> Dict[str, Any]:
    """Get update data from user"""
    console.print("\n[bold green]Enter fields to update (leave empty to skip)[/bold green]")
    
    update_data = {}
    
    name = Prompt.ask("New name (or press Enter to skip)", default="")
    if name:
        update_data["name"] = name
    
    prepayment_price = Prompt.ask("New prepayment price (or press Enter to skip)", default="")
    if prepayment_price:
        update_data["prepayment_price"] = float(prepayment_price)
    
    display_price = Prompt.ask("New display price (or press Enter to skip)", default="")
    if display_price:
        update_data["display_price"] = float(display_price)
    
    index = Prompt.ask("New index (or press Enter to skip)", default="")
    if index:
        update_data["index"] = int(index)
    
    min_booking_ahead_days = Prompt.ask("New min booking ahead days (or press Enter to skip)", default="")
    if min_booking_ahead_days:
        update_data["min_booking_ahead_days"] = int(min_booking_ahead_days)
    
    return update_data

def show_edge_cases():
    """Display edge cases that should be tested"""
    console.print("\n[bold yellow]🔍 IMPORTANT EDGE CASES TO TEST[/bold yellow]")
    console.print("\n[bold cyan]💰 Pricing & Inventory Validation:[/bold cyan]")
    console.print("• ❌ Prepayment > 0 without SGiMed inventory - Should FAIL")
    console.print("• ✅ Prepayment > 0 with valid SGiMed inventory - Should succeed")
    console.print("• ✅ Prepayment = 0 without SGiMed inventory - Should succeed")
    console.print("• ✅ Prepayment = 0 with SGiMed inventory - Should succeed")
    console.print("• ❌ Invalid SGiMed inventory ID - Should fail")
    console.print("• 🔍 Try negative prepayment price - Test validation")
    
    console.print("\n[bold cyan]🏢 Service Group Relationships:[/bold cyan]")
    console.print("• ❌ Invalid/non-existent service group ID - Should fail with 404")
    console.print("• ✅ Valid service groups with different types (NO_DETAIL, SINGLE, MULTIPLE)")
    console.print("• 🔍 Test with recently deleted service groups")
    
    console.print("\n[bold cyan]🏪 Branch Restrictions:[/bold cyan]")
    console.print("• ✅ No branch restrictions - Available everywhere")
    console.print("• ✅ Valid branch restrictions - Limited to specific branches")
    console.print("• 🔍 Invalid branch IDs in restrictions")
    console.print("• 🔍 Empty vs null branch restrictions array")
    
    console.print("\n[bold cyan]📋 Test Configuration:[/bold cyan]")
    console.print("• ✅ No test items - Should succeed")
    console.print("• ✅ Valid test items with name/exclusion")
    console.print("• 🔍 Empty test names or exclusions")
    console.print("• 🔍 Very long test names/exclusions")
    
    console.print("\n[bold cyan]🔢 Index & Ordering:[/bold cyan]")
    console.print("• 🔍 Duplicate index values across services")
    console.print("• 🔍 Negative index values")
    console.print("• 🔍 Very large index numbers (999999)")
    
    console.print("\n[bold cyan]📅 Booking Constraints:[/bold cyan]")
    console.print("• 🔍 min_booking_ahead_days = 0 (same day booking)")
    console.print("• 🔍 Very large min_booking_ahead_days (365+)")
    console.print("• 🔍 Negative min_booking_ahead_days")
    
    console.print("\n[bold cyan]🔄 Update Operations:[/bold cyan]")
    console.print("• ❌ Change prepayment 0→>0 without inventory - Should FAIL")
    console.print("• ✅ Change prepayment >0→0 - Should succeed")
    console.print("• ❌ Remove inventory when prepayment >0 - Should FAIL")
    console.print("• ❌ Change to invalid service group - Should fail")
    console.print("• ✅ Partial updates should preserve existing values")
    
    console.print("\n[bold cyan]🗑️ Delete Operations:[/bold cyan]")
    console.print("• 🔍 Delete service with existing appointments")
    console.print("• ❌ Delete non-existent service - Should return 404")
    console.print("• ❌ Delete same service twice - Should fail gracefully")
    
    console.print("\n[bold red]💡 Testing Tips:[/bold red]")
    console.print("• Use 'verify-db <id>' after each operation to check database state")
    console.print("• Test both happy paths (✅) and expected failures (❌)")
    console.print("• Pay special attention to pricing/inventory validation rules")
    console.print("• Try boundary values and malformed input")
    console.print("• Check API responses AND database consistency")

@app.command()
def test_crud(
    base_url: Annotated[str, typer.Option(help="Base URL of the API server")] = "/api/admin/appointments/v1",
    auto_cleanup: Annotated[bool, typer.Option("--auto-cleanup/--no-auto-cleanup", help="Automatically cleanup created records")] = True,
    show_edge_cases_flag: Annotated[bool, typer.Option("--show-edge-cases", help="Display edge cases before testing")] = True
):
    """Run the complete Service CRUD test suite"""
    
    console.print(Panel.fit(
        "[bold blue]Service CRUD Tester[/bold blue]\n"
        "This tool tests the Service CRUD operations via API calls\n"
        "and verifies database records are saved correctly.\n\n"
        "[yellow]💡 Use --show-edge-cases to see important test scenarios[/yellow]",
        border_style="blue"
    ))
    
    if show_edge_cases_flag:
        show_edge_cases()
        if not Confirm.ask("\n[bold]Continue with testing?[/bold]", default=True):
            raise typer.Exit(0)
    
    try:
        tester = ServiceTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_tests():
        try:
            # Test 1: Create Service
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 1: CREATE SERVICE[/bold cyan]")
            console.print("="*60)
            
            service_data = get_user_input()
            service_id = await tester.test_create_service(service_data)
            
            if not service_id:
                console.print("❌ [red]CREATE test failed, stopping here[/red]")
                return
            
            # Verify database record after creation
            tester.verify_database_record(service_id, service_data)
            
            # Test 2: Get Service
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 2: GET SERVICE[/bold cyan]")
            console.print("="*60)
            
            await tester.test_get_service(service_id)
            
            # Test 3: List All Services
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 3: LIST ALL SERVICES[/bold cyan]")
            console.print("="*60)
            
            await tester.test_list_services()
            
            # Test 4: Update Service
            if Confirm.ask("\nDo you want to test UPDATE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 4: UPDATE SERVICE[/bold cyan]")
                console.print("="*60)
                
                update_data = get_update_data()
                if update_data:
                    success = await tester.test_update_service(service_id, update_data)
                    if success:
                        # Verify database record after update
                        combined_data = {**service_data, **update_data}
                        tester.verify_database_record(service_id, combined_data)
                        
                        # Get updated record via API
                        await tester.test_get_service(service_id)
            
            # Test 5: Delete Service
            if Confirm.ask("\nDo you want to test DELETE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 5: DELETE SERVICE[/bold cyan]")
                console.print("="*60)
                
                delete_success = await tester.test_delete_service(service_id)
                
                if delete_success:
                    # Verify record is deleted from database
                    tester.verify_record_deleted(service_id)
            
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
    base_url: Annotated[str, typer.Option(help="Base URL of the API server")] = "/api/admin/appointments/v1",
    group_id: Annotated[Optional[str], typer.Option(help="Filter by service group ID")] = None
):
    """Only test the LIST operation to see existing services"""
    
    console.print("[bold blue]Listing all services...[/bold blue]")
    
    try:
        tester = ServiceTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_list():
        await tester.test_list_services(group_id)
    
    asyncio.run(run_list())

@app.command()
def edge_cases():
    """Display comprehensive edge cases and testing scenarios for Services"""
    show_edge_cases()

@app.command()
def verify_db(
    service_id: Annotated[str, typer.Argument(help="Service ID to verify in database")]
):
    """Verify a specific service exists in the database"""
    
    console.print(f"[bold blue]Verifying service {service_id} in database...[/bold blue]")
    
    try:
        with SessionLocal() as db:
            service = db.query(AppointmentService).filter(
                AppointmentService.id == service_id
            ).first()
            
            if not service:
                console.print("❌ [red]Service not found in database[/red]")
                raise typer.Exit(1)
            
            console.print("✅ [green]Service found in database[/green]")
            
            # Display details
            table = Table(title="Database Record Details")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("ID", str(service.id))
            table.add_row("Name", str(service.name))
            table.add_row("Prepayment Price", f"${service.prepayment_price}")
            table.add_row("Display Price", f"${service.display_price}")
            table.add_row("Index", str(service.index))
            table.add_row("Min Booking Ahead Days", str(service.min_booking_ahead_days))
            table.add_row("SGiMed Inventory ID", str(service.sgimed_inventory_id or "None"))
            table.add_row("Restricted Branches", str(service.restricted_branches))
            table.add_row("Tests", str(service.tests or "None"))
            table.add_row("Group ID", str(service.group_id))
            table.add_row("Created At", str(service.created_at))
            table.add_row("Updated At", str(service.updated_at))
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Database verification error: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()