#!/usr/bin/env python3
"""
CLI Service Group CRUD Tester

This CLI application allows testing the Service Group CRUD operations by:
1. Accepting user input for Service Group data
2. Making API calls to test CRUD operations
3. Verifying database records are saved correctly

Usage:
    uv run cli/service_group_tester.py
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
    from models.appointment import AppointmentServiceGroup
    from models.model_enums import AppointmentServiceGroupType
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
app = typer.Typer(help="CLI Service Group CRUD Tester")

from fastapi.testclient import TestClient
from routers.admin.utils import get_current_user
from main import app as fastapi_app
fastapi_app.dependency_overrides[get_current_user] = lambda: {"user_id": '123'}
client = TestClient(fastapi_app)

class ServiceGroupTester:
    def __init__(self, base_url: str = "/api/admin/appointments/v1"):
        self.base_url = base_url
        self.created_service_groups: List[str] = []  # Track created IDs for cleanup

    async def test_create_service_group(self, service_group_data: Dict[str, Any]) -> Optional[str]:
        """Test creating a service group via API"""
        console.print("\n[bold blue]Testing CREATE Service Group API[/bold blue]")
        
        try:
            response = client.post(
                f"{self.base_url}/service-groups",
                json=service_group_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                service_group_id = result.get("id")
                console.print(f"✅ [green]CREATE API Success: ID {service_group_id}[/green]")
                
                if service_group_id:
                    self.created_service_groups.append(service_group_id)
                
                return service_group_id
            else:
                console.print(f"❌ [red]CREATE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return None
                
        except Exception as e:
            console.print(f"❌ [red]CREATE API Error: {e}[/red]")
            return None
    
    async def test_get_service_group(self, service_group_id: str) -> Optional[Dict[str, Any]]:
        """Test getting a specific service group via API"""
        console.print(f"\n[bold blue]Testing GET Service Group API (ID: {service_group_id})[/bold blue]")
        
        try:
            response = client.get(
                f"{self.base_url}/service-groups/{service_group_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print("✅ [green]GET API Success[/green]")
                
                # Display service group details
                table = Table(title="Service Group Details")
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
    
    async def test_update_service_group(self, service_group_id: str, update_data: Dict[str, Any]) -> bool:
        """Test updating a service group via API"""
        console.print(f"\n[bold blue]Testing UPDATE Service Group API (ID: {service_group_id})[/bold blue]")
        
        try:
            response = client.put(
                f"{self.base_url}/service-groups/{service_group_id}",
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

    async def test_list_service_groups(self) -> Optional[List[Dict[str, Any]]]:
        """Test listing all service groups via API"""
        console.print("\n[bold blue]Testing LIST Service Groups API[/bold blue]")
        
        try:
            response = client.get(
                f"{self.base_url}/service-groups",
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                console.print(f"✅ [green]LIST API Success: Found {len(result)} service groups[/green]")
                
                # Display list in table format
                if result:
                    table = Table(title="All Service Groups")
                    table.add_column("ID", style="cyan", no_wrap=True)
                    table.add_column("Name", style="magenta")
                    table.add_column("Type", style="yellow")
                    table.add_column("Duration", style="green")
                    table.add_column("Index", style="blue")
                    
                    for group in result:
                        table.add_row(
                            str(group.get("id", ""))[:8] + "...",
                            str(group.get("name", "")),
                            str(group.get("type", "")),
                            f"{group.get('duration', 0)} min",
                            str(group.get("index", ""))
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
    
    async def test_delete_service_group(self, service_group_id: str) -> bool:
        """Test deleting a service group via API"""
        console.print(f"\n[bold blue]Testing DELETE Service Group API (ID: {service_group_id})[/bold blue]")
        
        try:
            response = client.delete(
                f"{self.base_url}/service-groups/{service_group_id}",
                timeout=30.0
            )
            
            if response.status_code == 200:
                console.print("✅ [green]DELETE API Success[/green]")
                if service_group_id in self.created_service_groups:
                    self.created_service_groups.remove(service_group_id)
                return True
            else:
                console.print(f"❌ [red]DELETE API Failed: {response.status_code}[/red]")
                console.print(f"Response: {response.text}")
                return False
                
        except Exception as e:
            console.print(f"❌ [red]DELETE API Error: {e}[/red]")
            return False

    def verify_database_record(self, service_group_id: str, expected_data: Dict[str, Any]) -> bool:
        """Verify that the service group record exists and matches expected data in database"""
        console.print(f"\n[bold blue]Verifying Database Record (ID: {service_group_id})[/bold blue]")
        
        try:
            with SessionLocal() as db:
                service_group = db.query(AppointmentServiceGroup).filter(
                    AppointmentServiceGroup.id == service_group_id
                ).first()
                
                if not service_group:
                    console.print("❌ [red]Database Verification Failed: Record not found[/red]")
                    return False
                
                console.print("✅ [green]Database Record Found[/green]")
                
                # Verify specific fields
                verification_results = []
                
                if "name" in expected_data:
                    matches = service_group.name == expected_data["name"]
                    verification_results.append(("name", service_group.name, expected_data["name"], matches))
                
                if "description" in expected_data:
                    matches = service_group.description == expected_data["description"]
                    verification_results.append(("description", service_group.description, expected_data["description"], matches))
                
                if "index" in expected_data:
                    matches = service_group.index == expected_data["index"]
                    verification_results.append(("index", service_group.index, expected_data["index"], matches))
                
                if "icon" in expected_data:
                    matches = service_group.icon == expected_data["icon"]
                    verification_results.append(("icon", service_group.icon, expected_data["icon"], matches))
                
                if "duration" in expected_data:
                    matches = service_group.duration == expected_data["duration"]
                    verification_results.append(("duration", service_group.duration, expected_data["duration"], matches))
                
                if "type" in expected_data:
                    expected_type = AppointmentServiceGroupType(expected_data["type"])
                    matches = service_group.type == expected_type
                    verification_results.append(("type", service_group.type.value, expected_data["type"], matches))
                
                if "restricted_branches" in expected_data:
                    matches = service_group.restricted_branches == expected_data["restricted_branches"]
                    verification_results.append(("restricted_branches", service_group.restricted_branches, expected_data["restricted_branches"], matches))
                
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
    
    def verify_record_deleted(self, service_group_id: str) -> bool:
        """Verify that a service group record has been deleted from the database"""
        console.print(f"\n[bold blue]Verifying record deletion from database[/bold blue]")
        try:
            with SessionLocal() as db:
                service_group = db.query(AppointmentServiceGroup).filter(
                    AppointmentServiceGroup.id == service_group_id
                ).first()
                
                if service_group is None:
                    console.print("✅ [green]Record successfully deleted from database[/green]")
                    return True
                else:
                    console.print("❌ [red]Record still exists in database[/red]")
                    return False
        except Exception as e:
            console.print(f"❌ [red]Error checking deletion: {e}[/red]")
            return False
    
    async def cleanup_created_records(self):
        """Clean up any service groups created during testing"""
        if not self.created_service_groups:
            return
            
        console.print(f"\n[bold yellow]Cleaning up {len(self.created_service_groups)} created service groups[/bold yellow]")
        
        for service_group_id in self.created_service_groups.copy():
            await self.test_delete_service_group(service_group_id)

def get_available_branches() -> List[Dict[str, str]]:
    """Get available branches from database"""
    try:
        with SessionLocal() as db:
            branches = db.query(Branch).filter(
                Branch.deleted == False,
                Branch.hidden == False
            ).order_by(Branch.name).all()
            return [{"id": str(branch.id), "name": branch.name, "sgimed_branch_id": branch.sgimed_branch_id} for branch in branches]
    except Exception as e:
        console.print(f"[red]Error fetching branches: {e}[/red]")
        return []

def get_user_input() -> Dict[str, Any]:
    """Get service group data from user input"""
    console.print("\n[bold green]Enter Service Group Information[/bold green]")
    
    name = Prompt.ask("Service Group Name", default="Test Service Group")
    description = Prompt.ask("Description (optional)", default="Test description for CLI testing")
    index = int(Prompt.ask("Index (sorting order)", default="1"))
    icon = Prompt.ask("Icon", default="medical")
    duration = int(Prompt.ask("Duration (minutes)", default="30"))
    
    # Service Group Type
    console.print("\nService Group Types:")
    console.print("1. NO_DETAIL - Simple service group without detailed selection")
    console.print("2. SINGLE - Allows selection of one service")
    console.print("3. MULTIPLE - Allows selection of multiple services")
    
    type_choice = Prompt.ask("Choose type", choices=["1", "2", "3"], default="1")
    type_mapping = {
        "1": "no_detail",
        "2": "single", 
        "3": "multiple"
    }
    service_type = type_mapping[type_choice]
    
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
                            restricted_branches.append(branches[idx]["sgimed_branch_id"])
                    console.print(f"Selected branches: {restricted_branches}")
                except (ValueError, IndexError):
                    console.print("[yellow]Invalid selection, skipping branch restrictions[/yellow]")
        else:
            console.print("[yellow]No branches found in database[/yellow]")
    
    return {
        "name": name,
        "description": description if description else None,
        "index": index,
        "icon": icon,
        "duration": duration,
        "type": service_type,
        "restricted_branches": restricted_branches
    }

def get_update_data() -> Dict[str, Any]:
    """Get update data from user"""
    console.print("\n[bold green]Enter fields to update (leave empty to skip)[/bold green]")
    
    update_data = {}
    
    name = Prompt.ask("New name (or press Enter to skip)", default="")
    if name:
        update_data["name"] = name
    
    description = Prompt.ask("New description (or press Enter to skip)", default="")
    if description:
        update_data["description"] = description
    
    index = Prompt.ask("New index (or press Enter to skip)", default="")
    if index:
        update_data["index"] = int(index)
    
    duration = Prompt.ask("New duration (or press Enter to skip)", default="")
    if duration:
        update_data["duration"] = int(duration)
    
    return update_data

def show_service_group_edge_cases():
    """Display edge cases that should be tested for Service Groups"""
    console.print("\n[bold yellow]🔍 SERVICE GROUP EDGE CASES TO TEST[/bold yellow]")
    console.print("\n[bold cyan]🏢 Service Group Types:[/bold cyan]")
    console.print("• ✅ NO_DETAIL - Simple group without detailed selection")
    console.print("• ✅ SINGLE - Allows selection of one service")
    console.print("• ✅ MULTIPLE - Allows selection of multiple services")
    console.print("• 🔍 Test behavior differences between types")
    
    console.print("\n[bold cyan]🔢 Index & Ordering:[/bold cyan]")
    console.print("• 🔍 Duplicate index values across service groups")
    console.print("• 🔍 Negative index values")
    console.print("• 🔍 Very large index numbers (999999)")
    console.print("• ✅ Zero index value")
    
    console.print("\n[bold cyan]⏱️ Duration Validation:[/bold cyan]")
    console.print("• 🔍 Zero duration - Should this be allowed?")
    console.print("• 🔍 Negative duration - Should be caught by validation")
    console.print("• 🔍 Very large duration (999+ minutes)")
    console.print("• ✅ Typical durations (15, 30, 45, 60 minutes)")
    
    console.print("\n[bold cyan]🏪 Branch Restrictions:[/bold cyan]")
    console.print("• ✅ No branch restrictions - Available everywhere")
    console.print("• ✅ Valid branch restrictions - Limited to specific branches")
    console.print("• 🔍 Invalid branch IDs in restrictions")
    console.print("• 🔍 Empty vs null branch restrictions array")
    console.print("• 🔍 All branches restricted vs no restrictions")
    
    console.print("\n[bold cyan]🏢 Corporate Code Integration:[/bold cyan]")
    console.print("• ✅ No corporate code - Available to all")
    console.print("• ✅ Valid corporate code - Restricted to corporate users")
    console.print("• ❌ Invalid corporate code ID - Should fail")
    console.print("• 🔍 Test with expired corporate codes")
    
    console.print("\n[bold cyan]📝 Name & Description:[/bold cyan]")
    console.print("• ✅ Normal names and descriptions")
    console.print("• 🔍 Very long names (255+ characters)")
    console.print("• 🔍 Empty/null descriptions")
    console.print("• 🔍 Special characters in names")
    console.print("• 🔍 Duplicate service group names")
    
    console.print("\n[bold cyan]🎨 Icon Validation:[/bold cyan]")
    console.print("• ✅ Standard icon names")
    console.print("• 🔍 Invalid/non-existent icon names")
    console.print("• 🔍 Empty icon strings")
    console.print("• 🔍 Very long icon strings")
    
    console.print("\n[bold cyan]🔄 Update Operations:[/bold cyan]")
    console.print("• ✅ Update individual fields")
    console.print("• ✅ Update multiple fields at once")
    console.print("• ❌ Update to invalid corporate code - Should fail")
    console.print("• 🔍 Update service group type with existing services")
    console.print("• 🔍 Partial updates should preserve existing values")
    
    console.print("\n[bold cyan]🗑️ Delete Operations:[/bold cyan]")
    console.print("• ❌ Delete service group with existing services - Should FAIL")
    console.print("• ✅ Delete service group with no services - Should succeed")
    console.print("• ❌ Delete non-existent service group - Should return 404")
    console.print("• ❌ Delete same service group twice - Should fail gracefully")
    
    console.print("\n[bold cyan]🔗 Data Relationships:[/bold cyan]")
    console.print("• 🔍 Create services in different service group types")
    console.print("• 🔍 Corporate code deletion with linked service groups")
    console.print("• 🔍 Branch deletion with service groups restricted to it")
    
    console.print("\n[bold red]💡 Testing Tips:[/bold red]")
    console.print("• Use 'verify-db <id>' after each operation to check database state")
    console.print("• Test both happy paths (✅) and expected failures (❌)")
    console.print("• Create service groups BEFORE testing services (services need groups)")
    console.print("• Pay attention to the relationship between group type and service behavior")
    console.print("• Check API responses AND database consistency")

@app.command()
def edge_cases():
    """Display comprehensive edge cases and testing scenarios for Service Groups"""
    show_service_group_edge_cases()

@app.command()
def test_crud(
    base_url: Annotated[str, typer.Option(help="Base URL of the API server")] = "/api/admin/appointments/v1",
    auto_cleanup: Annotated[bool, typer.Option("--auto-cleanup/--no-auto-cleanup", help="Automatically cleanup created records")] = True,
    show_edge_cases_flag: Annotated[bool, typer.Option("--show-edge-cases", help="Display edge cases before testing")] = True
):
    """Run the complete Service Group CRUD test suite"""
    
    console.print(Panel.fit(
        "[bold blue]Service Group CRUD Tester[/bold blue]\n"
        "This tool tests the Service Group CRUD operations via API calls\n"
        "and verifies database records are saved correctly.\n\n"
        "[yellow]💡 Use --show-edge-cases to see important test scenarios[/yellow]",
        border_style="blue"
    ))
    
    if show_edge_cases_flag:
        show_service_group_edge_cases()
        if not Confirm.ask("\n[bold]Continue with testing?[/bold]", default=True):
            raise typer.Exit(0)
    
    try:
        tester = ServiceGroupTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_tests():
        try:
            # Test 1: Create Service Group
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 1: CREATE SERVICE GROUP[/bold cyan]")
            console.print("="*60)
            
            service_group_data = get_user_input()
            service_group_id = await tester.test_create_service_group(service_group_data)
            
            if not service_group_id:
                console.print("❌ [red]CREATE test failed, stopping here[/red]")
                return
            
            # Verify database record after creation
            tester.verify_database_record(service_group_id, service_group_data)
            
            # Test 2: Get Service Group
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 2: GET SERVICE GROUP[/bold cyan]")
            console.print("="*60)
            
            await tester.test_get_service_group(service_group_id)
            
            # Test 3: List All Service Groups
            console.print("\n" + "="*60)
            console.print("[bold cyan]TEST 3: LIST ALL SERVICE GROUPS[/bold cyan]")
            console.print("="*60)
            
            await tester.test_list_service_groups()
            
            # Test 4: Update Service Group
            if Confirm.ask("\nDo you want to test UPDATE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 4: UPDATE SERVICE GROUP[/bold cyan]")
                console.print("="*60)
                
                update_data = get_update_data()
                if update_data:
                    success = await tester.test_update_service_group(service_group_id, update_data)
                    if success:
                        # Verify database record after update
                        combined_data = {**service_group_data, **update_data}
                        tester.verify_database_record(service_group_id, combined_data)
                        
                        # Get updated record via API
                        await tester.test_get_service_group(service_group_id)
            
            # Test 5: Delete Service Group
            if Confirm.ask("\nDo you want to test DELETE operation?", default=True):
                console.print("\n" + "="*60)
                console.print("[bold cyan]TEST 5: DELETE SERVICE GROUP[/bold cyan]")
                console.print("="*60)
                
                delete_success = await tester.test_delete_service_group(service_group_id)
                
                if delete_success:
                    # Verify record is deleted from database
                    tester.verify_record_deleted(service_group_id)
            
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
    """Only test the LIST operation to see existing service groups"""
    
    console.print("[bold blue]Listing all service groups...[/bold blue]")
    
    try:
        tester = ServiceGroupTester(base_url)
    except Exception as e:
        console.print(f"[red]Failed to initialize tester: {e}[/red]")
        raise typer.Exit(1)
    
    async def run_list():
        await tester.test_list_service_groups()
    
    asyncio.run(run_list())

@app.command()
def verify_db(
    service_group_id: Annotated[str, typer.Argument(help="Service Group ID to verify in database")]
):
    """Verify a specific service group exists in the database"""
    
    console.print(f"[bold blue]Verifying service group {service_group_id} in database...[/bold blue]")
    
    try:
        with SessionLocal() as db:
            service_group = db.query(AppointmentServiceGroup).filter(
                AppointmentServiceGroup.id == service_group_id
            ).first()
            
            if not service_group:
                console.print("❌ [red]Service group not found in database[/red]")
                raise typer.Exit(1)
            
            console.print("✅ [green]Service group found in database[/green]")
            
            # Display details
            table = Table(title="Database Record Details")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="magenta")
            
            table.add_row("ID", str(service_group.id))
            table.add_row("Name", str(service_group.name))
            table.add_row("Description", str(service_group.description or "None"))
            table.add_row("Index", str(service_group.index))
            table.add_row("Icon", str(service_group.icon))
            table.add_row("Duration", f"{service_group.duration} minutes")
            table.add_row("Type", str(service_group.type.value))
            table.add_row("Restricted Branches", str(service_group.restricted_branches))
            table.add_row("Created At", str(service_group.created_at))
            table.add_row("Updated At", str(service_group.updated_at))
            
            console.print(table)
            
    except Exception as e:
        console.print(f"[red]Database verification error: {e}[/red]")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()