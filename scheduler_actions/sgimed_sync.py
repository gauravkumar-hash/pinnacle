import logging
from datetime import datetime
from sqlalchemy.orm import Session

from models import SGiMedInventory
from models.sgimed import SGiMedAppointmentType
from .common import CronLogAPI


def update_inventory_sync_cron(db: Session):
    """
    Sync inventory items from SGiMed using CronLogAPI pattern
    """
    cron = CronLogAPI(db, 'sgimed_inventory_sync_cron', '/inventory')
    if len(cron.data) == 0:
        return

    created_cnts = 0
    updated_cnts = 0
    existing_cnts = 0
    failed_cnts = 0
    duplicated_cnts = 0

    # Get existing inventory IDs and last edited times
    unique_ids = set([row['id'] for row in cron.data])
    existing_records = db.query(SGiMedInventory.id, SGiMedInventory.last_edited).filter(
        SGiMedInventory.id.in_(unique_ids)
    ).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}
    processed = []

    for row in cron.data:
        try:
            # Parse dates
            last_edited = None
            created_at = None
            if row.get('last_edited'):
                last_edited = datetime.strptime(row['last_edited'], "%Y-%m-%d %H:%M:%S")
            if row.get('created_at'):
                created_at = datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S")
            
            # Extract category info
            category_id = row.get('category', {}).get('id') if row.get('category') else ''
            # if category_id is None:
            #     raise Exception("Failed inventory without category id: ", row)

            # If duplicated, skip
            if row['id'] in processed:
                duplicated_cnts += 1
                continue

            # Check for existing record
            if row['id'] in existing_records_map:
                existing_cnts += 1
                # Check if record has been updated
                if existing_records_map[row['id']] and last_edited and created_at:
                    if existing_records_map[row['id']].strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
                        # Update existing record
                        inventory = db.query(SGiMedInventory).filter(SGiMedInventory.id == row['id']).first()
                        if inventory:
                            inventory.code = row['code']
                            inventory.name = row['name']
                            inventory.type = row['type']
                            inventory.remark = row.get('remark')
                            inventory.is_stock_tracked = row.get('is_stock_tracked', False)
                            inventory.last_edited = last_edited
                            inventory.created_at = created_at
                            inventory.category_id = category_id
                            inventory.inventory_json = None
                            updated_cnts += 1
                continue
            
            # Create new record
            created_cnts += 1
            inventory = SGiMedInventory(
                id=row['id'],
                code=row['code'],
                name=row['name'],
                type=row['type'],
                remark=row.get('remark'),
                is_stock_tracked=row.get('is_stock_tracked', False),
                last_edited=last_edited,
                created_at=created_at,
                category_id=category_id
            )
            processed.append(row['id'])
            db.add(inventory)
            
        except Exception as e:
            failed_cnts += 1
            logging.error(f'Failed to sync inventory item {row.get("id", "unknown")}: {str(e)}')
            continue
    
    cron.commit()
    print(f"Inventory Sync Cron: {cron.cron_log.last_modified}, Created {created_cnts}, Updated {updated_cnts}, Existing {existing_cnts}, Failed {failed_cnts}, Duplicated: {duplicated_cnts}")


def update_appointment_types_sync_cron(db: Session):
    """
    Sync appointment types from SGiMed using CronLogAPI pattern
    """
    cron = CronLogAPI(db, 'sgimed_appointment_types_sync_cron', '/appointment-type')
    if len(cron.data) == 0:
        return
    
    created_cnts = 0
    updated_cnts = 0
    existing_cnts = 0
    failed_cnts = 0
    
    # Get existing appointment type IDs and last edited times
    unique_ids = set([row['id'] for row in cron.data])
    existing_records = db.query(SGiMedAppointmentType.id, SGiMedAppointmentType.last_edited).filter(
        SGiMedAppointmentType.id.in_(unique_ids)
    ).all()
    existing_records_map = {row[0]: row[1] for row in existing_records}
    
    for row in cron.data:
        try:
            # Parse dates
            last_edited = None
            created_at = None
            if row.get('last_edited'):
                last_edited = datetime.strptime(row['last_edited'], "%Y-%m-%d %H:%M:%S")
            if row.get('created_at'):
                created_at = datetime.strptime(row['created_at'], "%Y-%m-%d %H:%M:%S")
            
            # Check for existing record
            if row['id'] in existing_records_map:
                existing_cnts += 1
                # Check if record has been updated
                if existing_records_map[row['id']] and last_edited:
                    if existing_records_map[row['id']].strftime("%Y-%m-%d %H:%M:%S") != row['last_edited']:
                        # Update existing record
                        appointment_type = db.query(SGiMedAppointmentType).filter(SGiMedAppointmentType.id == row['id']).first()
                        if appointment_type and created_at:
                            appointment_type.name = row['name']
                            appointment_type.branch_id = row['branch_id']
                            appointment_type.sort_key = row.get('sort_key') if row.get('sort_key') else 0
                            appointment_type.is_enabled = row.get('is_enabled', True)
                            appointment_type.is_for_visit = row.get('is_for_visit', False)
                            appointment_type.is_for_appointment = row.get('is_for_appointment', True)
                            appointment_type.is_block_type = row.get('is_block_type', False)
                            appointment_type.last_edited = last_edited
                            appointment_type.created_at = created_at
                            updated_cnts += 1
                continue
            
            # Create new record
            created_cnts += 1
            appointment_type = SGiMedAppointmentType(
                id=row['id'],
                name=row['name'],
                branch_id=row['branch_id'],
                sort_key=row.get('sort_key') if row.get('sort_key') else 0,
                is_enabled=row.get('is_enabled', True),
                is_for_visit=row.get('is_for_visit', False),
                is_for_appointment=row.get('is_for_appointment', True),
                is_block_type=row.get('is_block_type', False),
                last_edited=last_edited,
                created_at=created_at
            )
            db.add(appointment_type)
            
        except Exception as e:
            failed_cnts += 1
            logging.error(f'Failed to sync appointment type {row.get("id", "unknown")}: {str(e)}')
            continue
    
    cron.commit()
    print(f"Appointment Types Sync Cron: {cron.cron_log.last_modified}, Created {created_cnts}, Updated {updated_cnts}, Existing {existing_cnts}, Failed {failed_cnts}")


def update_inventory_details_cron(db: Session):
    """
    Update inventory details (price and inventory_json) from SGiMed for records where inventory_json is null
    """
    from utils.integrations.sgimed import get
    
    # Fetch 5 records where inventory_json is null
    inventory_records = db.query(SGiMedInventory).filter(
        SGiMedInventory.inventory_json.is_(None)
    ).limit(5).all()
    
    if not inventory_records:
        print("No inventory records with null inventory_json found")
        return
    
    updated_count = 0
    failed_count = 0
    
    for record in inventory_records:
        try:
            # Call SGiMed endpoint GET /inventory/{inventory_id}
            inventory_data = get(f'/inventory/{record.id}')
            
            if inventory_data and 'data' in inventory_data and inventory_data['data']:
                # Store the first row in inventory_json
                first_row = inventory_data['data'][0]
                record.inventory_json = first_row
                
                # Extract selling_price for price column
                if 'selling_price' in first_row and first_row['selling_price'] is not None:
                    try:
                        record.price = float(first_row['selling_price'])
                    except (ValueError, TypeError):
                        logging.warning(f"Could not convert selling_price to float for inventory {record.id}: {first_row['selling_price']}")
                        record.price = None
                else:
                    record.price = None
                
                updated_count += 1
                logging.info(f"Updated inventory {record.id} with price {record.price}")
            else:
                logging.warning(f"No data returned from SGiMed for inventory {record.id}")
                
        except Exception as e:
            failed_count += 1
            logging.error(f"Failed to update inventory details for {record.id}: {str(e)}")
            continue
    
    # Commit all changes
    db.commit()
    print(f"Inventory Details Update Cron: Updated {updated_count}, Failed {failed_count}")