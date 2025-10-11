import openpyxl
import csv


def get_xlsx_table(tables: list[list], name: str) -> str:
    """
        Возвращает путь к файлу таблицы
    """
    wb = openpyxl.Workbook()
    sheet = wb.active

    for row in range(0, len(tables)):
        for column in range(0, len(tables[row])):
            c = sheet.cell(row=row + 1, column=column + 1)
            c.value = tables[row][column]
    wb.save(f'{name}.xlsx')
    return f'{name}.xlsx'


def get_csv_table(tables: list[list], name: str) -> str:
    filename = f'{name}.csv'

    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Записываем все строки таблицы
        for row in tables:
            writer.writerow(row)

    return filename
