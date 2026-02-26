# Change XLS/XLSX to CSV converter: https://stackoverflow.com/a/9886039/6944050
# Pandas to_sql vs COPY
# https://towardsdatascience.com/upload-your-pandas-dataframe-to-your-database-10x-faster-eb6dc6609ddf
# CSV COPY to database
# https://stackoverflow.com/a/34523707/6944050
# Openpyxl vs XLRD Performance
# https://stackoverflow.com/q/35823835/6944050

# 1. Convert XLSX to CSV
# 2. Upload CSV to Postgres
# 3. Compare for Changes
# 4. Execute Changes

from fastapi import HTTPException
import openpyxl
import csv
from models import engine
from models.pinnacle import StAndrew, StAndrewMetadata, StAndrewTemp

existing_table_name = StAndrew.__tablename__
temp_table_name = StAndrewTemp.__tablename__
    
def convert_xlsx_to_csv(input_xlsx, output_csv):
    wb = openpyxl.load_workbook(input_xlsx)
    sh = wb.active
    if sh:
        with open(output_csv, 'w', newline="") as file_handle:
            csv_writer = csv.writer(file_handle)
            for row in sh.iter_rows(): # generator; was sh.rows
                csv_writer.writerow([cell.value for cell in row])
    wb.close()

def upload_csv(csv_file_path, table_name = temp_table_name):
    
    copy_cmd = f'''
    COPY {table_name}
    (comp_code,company_name,uen,employee_no,employee_name,nric,passport,sector,pcp_start,pcp_end,checkup_mwoc,status,created_date_time,termination_date,handphone_no)
    FROM STDIN WITH (FORMAT CSV, HEADER TRUE)
    '''

    try:
        with open(csv_file_path, 'r') as f:    
            conn = engine.raw_connection()
            cursor = conn.cursor()
            cursor.execute(f'TRUNCATE TABLE {table_name}')
            cursor.copy_expert(copy_cmd, f)
            conn.commit()
            conn.close()
    except Exception as e:
        raise HTTPException(500, f"Error uploading CSV: {e}")

def compare_tables():
    compare_existing = f'''
    select tbl1.nric as row_tbl1, tbl2.nric as row_tbl2
    from {existing_table_name} as tbl1
    full outer join {temp_table_name} as tbl2
    ON row(tbl1)=row(tbl2)
    WHERE tbl1.nric is null or tbl2.nric is null;
    '''
    
    conn = engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute(compare_existing)
    results = cursor.fetchall()
    conn.close()

    none = set([None])
    old = set(map(lambda x: x[0], results)) - none
    new = set(map(lambda x: x[1], results)) - none

    new_records = new - old
    updated_records = new & old
    deleted_records = old - new

    # print(f"New: {len(new_records)}")
    # print(f"Updated: {len(updated_records)}")
    # print(f"Deleted: {len(deleted_records)}")

    return new_records, updated_records, deleted_records
    
def overwrite_changes(record: StAndrewMetadata):
    # Inserting records from another table https://stackoverflow.com/a/8671854/6944050

    conn = engine.raw_connection()
    cursor = conn.cursor()
    
    new = set(record.insert_diff)
    updated = set(record.update_diff)
    deleted = set(record.delete_diff)
    
    old_records = tuple(deleted | updated)
    new_records = tuple(new | updated)

    if old_records:
        print(cursor.mogrify(f'DELETE FROM {existing_table_name} WHERE nric in %s', (old_records,)))
        cursor.execute(f'DELETE FROM {existing_table_name} WHERE nric in %s', (old_records,))
    if new_records:
        print(cursor.mogrify(f'INSERT into {existing_table_name} select * from {temp_table_name} where nric in %s', (new_records,)))
        cursor.execute(f'INSERT into {existing_table_name} select * from {temp_table_name} where nric in %s', (new_records,))

    conn.commit()
    conn.close()
