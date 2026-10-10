import openpyxl
import pandas as pd
import os
import re

def convert_excel_to_csv(excel_path, output_csv_path="cartelera_plana.csv"):
    if not os.path.exists(excel_path):
        print(f"⚠️ El archivo '{excel_path}' no existe.")
        return

    # Si el archivo es CSV guardado como .xlsx o viceversa, lo manejamos dinámicamente
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    sheet = wb.active

    races_data = []
    current_race_num = None
    current_fecha = ""
    current_hora = ""

    for row_idx in range(1, sheet.max_row + 1):
        # Obtener los datos de toda la fila como lista
        row_vals = [sheet.cell(row=row_idx, column=col).value for col in range(1, sheet.max_column + 1)]
        row_str = [str(val).strip() if val is not None else "" for val in row_vals]

        # 1. Detectar el bloque de la carrera
        for col_idx, cell_text in enumerate(row_str):
            if "carrera nro" in cell_text.lower():
                # En el Excel el número de carrera está en la fila de abajo en esa columna
                val_below = sheet.cell(row=row_idx + 1, column=col_idx + 1).value
                if val_below is not None and str(val_below).strip().isdigit():
                    current_race_num = int(str(val_below).strip())
                else:
                    # O buscar el número en la misma celda
                    match = re.search(r'\d+', cell_text)
                    if match:
                        current_race_num = int(match.group(0))

            if "fecha:" in cell_text.lower():
                val_below = sheet.cell(row=row_idx + 1, column=col_idx + 1).value
                if val_below is not None:
                    current_fecha = str(val_below).strip()

            if "hora:" in cell_text.lower():
                val_below = sheet.cell(row=row_idx + 1, column=col_idx + 1).value
                if val_below is not None:
                    current_hora = str(val_below).strip()

        # 2. Ignorar el encabezado de la tabla (N° | Ejemplar | Medic. | ...)
        if len(row_str) >= 2 and row_str[0].upper() == "N°" and "EJEMPLAR" in row_str[1].upper():
            continue

        # 3. Extraer ejemplares cuando la columna N° contiene un número (1, 2, 3...)
        first_col = row_str[0] if len(row_str) > 0 else ""
        if first_col.isdigit() and len(row_str) >= 2:
            horse_num = int(first_col)
            raw_horse_name = row_str[1]
            
            # Limpiar nombre si trae saltos de línea internos (ej. precios/reclamos)
            clean_horse_name = raw_horse_name.split('\n')[0].strip()

            if clean_horse_name and current_race_num is not None:
                races_data.append({
                    "numero_caballo": horse_num,
                    "nombre_caballo": clean_horse_name,
                    "numero_carrera": current_race_num,
                    "fecha": current_fecha,
                    "hora": current_hora
                })

    if not races_data:
        print("⚠️ No se pudieron extraer ejemplares. Verifica que el archivo no esté vacío.")
        return

    # Guardar en CSV plano UTF-8
    df = pd.DataFrame(races_data)
    df.to_csv(output_csv_path, index=False, encoding="utf-8")
    
    num_carreras = len(df['numero_carrera'].unique())
    print(f"✅ ¡Éxito! Se procesaron {len(races_data)} ejemplares en {num_carreras} carreras.")
    print(f"📄 Archivo generado: {os.path.abspath(output_csv_path)}")

if __name__ == "__main__":
    archivo_excel = "Ejemplares inscritos reunión 39.xlsx"
    
    # Buscar el archivo en la carpeta si cambia levemente el nombre
    if not os.path.exists(archivo_excel):
        for f in os.listdir("."):
            if f.endswith(".xlsx") and not f.startswith("~$"):
                archivo_excel = f
                break

    if os.path.exists(archivo_excel):
        print(f"📊 Procesando: {archivo_excel}")
        convert_excel_to_csv(archivo_excel)
    else:
        print("⚠️ No se encontró el archivo Excel (.xlsx) en esta carpeta.")