from bs4 import BeautifulSoup
import re
import pandas as pd

def apj_tt(filename):

    with open(filename, "r", encoding = "utf-8") as file:
        html = file.read()

    soup = BeautifulSoup(html , "html.parser")

    tables = soup.find_all("table")
    table = tables[1]

    rows = table.find_all("tr")
    room_info = rows[0].get_text(" ", strip=True) # Extract room number and academic year

    room = re.search(r"APJ-\d+", room_info).group()
    academic_year = re.search(r"\d{4}-\d{2}", room_info).group()

    headers = rows[1].find_all(["td", "th"])  # Extract time slot headings
    slots = [cell.get_text(" ", strip=True) for cell in headers[1:12]]

    timetable = []

    for row in rows[2:-1]:

        cells = row.find_all(["td", "th"])
        day = cells[0].get_text(" ", strip=True)

        for slot, cell in zip(slots, cells[1:12]):

            class_info = cell.get_text(" ", strip=True)

            record = {
                "room": room,
                "academic_year": academic_year,
                "day": day,
                "slot": slot,
                "class_info": class_info if class_info else None
            }
            
            timetable.append(record)

    return timetable

all_timetables = []

for i in range(1, 11):

    filename = f"apj{i:02}.html"
    data = apj_tt(filename)
    all_timetables.extend(data)


df = pd.DataFrame(all_timetables)

df.to_csv("timetable.csv", index=False)

