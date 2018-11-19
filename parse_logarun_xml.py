# Code based on: https://www.geeksforgeeks.org/xml-parsing-python/
# Python code to illustrate parsing of XML files 
# importing the required modules 
import csv 
import requests 
import xml.etree.ElementTree as ET
from datetime import datetime

def parseXML(xmlfile): 

    # create element tree object 
    tree = ET.parse(xmlfile) 

    # get root element 
    root = tree.getroot() 

    # create empty list for runs
    runs = [] 

    # iterate day items 
    for day in root.findall('./dayItems/dayItem'): 

        for item in day: 
            simple_date = day.attrib['date']  # mm/dd/yyyy
            date = datetime.strptime(simple_date, '%m/%d/%Y')

            if item.attrib['exercise'] == 'Run':
                run = {}
                run['date'] = date.isoformat()
                run['mileage'] = item.attrib['value1']
                run['time'] = item.attrib['value2']
                run['shoe'] = item.attrib['value3']
                runs.append(run)

    # return list of runs
    return runs


def save_to_csv(items, filename, fields): 

    # writing to csv file 
    with open(filename, 'w') as csvfile: 

        # creating a csv dict writer object 
        writer = csv.DictWriter(csvfile, fieldnames = fields) 

        # writing headers (field names) 
        writer.writeheader() 

        # writing data rows 
        writer.writerows(items) 

    
def main(): 
    runs = parseXML('logarun.xml')

    save_to_csv(runs, 'logarun.csv', ['date','mileage', 'time', 'shoe'])

    
if __name__ == "__main__": 

    # calling main function 
    main() 
