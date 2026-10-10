import sqlite3
import sys

def dump_schema_and_data(db_path, output_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Dump schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name")
        schema_rows = cursor.fetchall()
        for row in schema_rows:
            f.write(row[0] + ';\n\n')
        
        # Dump data for duel_types
        f.write('-- Data for duel_types table\n')
        cursor.execute("SELECT * FROM duel_types")
        rows = cursor.fetchall()
        if rows:
            col_names = [description[0] for description in cursor.description]
            for row in rows:
                formatted_values = []
                for v in row:
                    if v is None:
                        formatted_values.append('NULL')
                    elif isinstance(v, str):
                        escaped = v.replace("'", "''")
                        formatted_values.append(f"'{escaped}'")
                    else:
                        formatted_values.append(str(v))
                f.write(f"INSERT INTO duel_types ({', '.join(col_names)}) VALUES ({', '.join(formatted_values)});\n")
        else:
            f.write('-- No data found in duel_types\n')
    
    conn.close()
    print(f'Dump written to {output_path}')

if __name__ == '__main__':
    db_path = 'backend/banca_hipica.db'
    output_path = 'backend/dump_duel_types.sql'
    dump_schema_and_data(db_path, output_path)
