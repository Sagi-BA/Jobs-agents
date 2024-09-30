import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

# שאר הייבוא נשאר ללא שינוי
import io
import pandas as pd
from dotenv import load_dotenv
import urllib.parse
from bs4 import BeautifulSoup
import json
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
import base64

load_dotenv()

# Read the existing agents.json file
# Load agents from JSON file
with open('agents.json', 'r', encoding='utf-8') as file:
    agents = json.load(file)

# # Find the Drushim agent
# drushim_agent = next((agent for agent in agents if agent['name'] == 'drushim'), None)

# if not drushim_agent:
#     raise ValueError("Drushim agent not found in agents.json")

def request_url(agent, prompt, page=1):
    driver = get_driver()
    base_url = agent['url']
    start_text = agent['start_text']
    end_text = agent['end_text']
    
    encoded_prompt = urllib.parse.quote(prompt)
    if '{page}' in base_url:
        url = base_url.format(prompt=encoded_prompt, page=page)
    else:
        url = base_url.format(prompt=encoded_prompt)
    
    try:
        driver.get(url)
        content = driver.page_source
        
        start_index = content.find(start_text)
        end_index = content.find(end_text, start_index)

        if start_index != -1 and end_index != -1:
            extracted_content = content[start_index:end_index + len(end_text)]
            return extracted_content
        else:
            st.warning(f"לא נמצא תוכן מתאים עבור {agent['name']}")
            return None

    except Exception as e:
        st.error(f"אירעה שגיאה בעת שליפת נתונים מ-{agent['name']}: {str(e)}")
        return None
    finally:
        driver.quit()

def extract_jobs_drushim(html_content, agent_name):
    soup = BeautifulSoup(html_content, 'html.parser')
    jobs = []
    
    for job_div in soup.find_all('div', class_='job-item-main'):
        job = {'source': agent_name}  # Add the agent name to each job
        
        # תפקיד
        title = job_div.find('h3', class_='display-28')
        job['title'] = title.text.strip() if title else ''
        
        # חברה
        company = job_div.find('p', class_='display-22')
        job['company'] = company.text.strip() if company else ''
        
        # מיקום, שנות ניסיון, היקף משרה, פורסם לפני
        details = job_div.find_all('span', class_='display-18')
        for detail in details:
            text = detail.text.strip()
            if 'שנים' in text:
                job['experience'] = text
            elif any(word in text for word in ['משרה מלאה', 'משרה חלקית']):
                job['job_type'] = text
            elif 'לפני' in text:
                job['posted'] = text
            else:
                job['location'] = text
        
        jobs.append(job)
    
    return jobs
def extract_jobs_jobmaster(html_content, agent_name):
    soup = BeautifulSoup(html_content, 'html.parser')
    jobs = []
    
    for job_div in soup.find_all('article', class_='JobItem'):
        job = {'source': agent_name}  # Add the agent name to each job
        
        # תפקיד (Title)
        title = job_div.find('a', class_='CardHeader')
        job['title'] = title.text.strip() if title else ''
        
        # חברה (Company)
        company = job_div.find('a', class_='CompanyNameLink') or job_div.find('span', class_='ByTitle')
        job['company'] = company.text.strip() if company else ''
        
        # מיקום (Location)
        location = job_div.find('li', class_='jobLocation')
        job['location'] = location.text.strip() if location else ''
        
        # שנות ניסיון (Experience)
        # JobMaster doesn't seem to have a specific field for experience, so we'll leave it empty
        job['experience'] = ''
        
        # היקף משרה (Job Type)
        job_type = job_div.find('li', class_='jobType')
        job['job_type'] = job_type.text.strip() if job_type else ''
        
        # פורסם לפני (Posted)
        posted = job_div.find('span', class_='Gray')
        job['posted'] = posted.text.strip() if posted else ''
        
        # תיאור קצר (Short Description)
        description = job_div.find('div', class_='jobShortDescription')
        job['description'] = description.text.strip() if description else ''
        
        jobs.append(job)
    
    return jobs
def create_excel_from_json(jobs):
    wb = Workbook()
    ws = wb.active
    ws.title = "רשימת משרות"

    headers = ['מקור', 'תפקיד', 'חברה', 'מיקום', 'ניסיון', 'סוג משרה', 'פורסם']

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    for row, job in enumerate(jobs, start=2):
        ws.cell(row=row, column=1, value=job.get('source', ''))
        ws.cell(row=row, column=2, value=job.get('title', ''))
        ws.cell(row=row, column=3, value=job.get('company', ''))
        ws.cell(row=row, column=4, value=job.get('location', ''))
        ws.cell(row=row, column=5, value=job.get('experience', ''))
        ws.cell(row=row, column=6, value=job.get('job_type', ''))
        ws.cell(row=row, column=7, value=job.get('posted', ''))

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width

    return wb

def get_table_download_link(df):
    """Generates a link allowing the data in a given panda dataframe to be downloaded"""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='openpyxl')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.save()
    processed_data = output.getvalue()
    b64 = base64.b64encode(processed_data).decode()
    return f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="job_listings.xlsx">Download Excel file</a>'

def main():
    st.set_page_config(layout="wide", page_title="סוכן משרות מקצועי", page_icon="🔍")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@400;700&display=swap');
    
    body {
        direction: rtl;
        text-align: right;
        font-family: 'Heebo', sans-serif;
    }
    .stButton>button {
        width: 100%;
    }
    .stSelectbox>div>div>select {
        direction: rtl;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("סוכן משרות מקצועי")

    selected_agents = st.multiselect("בחר סוכנים", [agent['name'] for agent in agents], default=[agent['name'] for agent in agents])
    prompt = st.text_input("הכנס מילות חיפוש", value="מנהל שיווק ומכירות")

    if st.button("חפש משרות"):
        if not selected_agents:
            st.warning("אנא בחר לפחות סוכן אחד")
            return

        progress_bar = st.progress(0)
        status_text = st.empty()

        all_jobs = []
        for i, agent_name in enumerate(selected_agents):
            agent = next((a for a in agents if a['name'] == agent_name), None)
            if agent:
                status_text.text(f"מחפש משרות ב-{agent_name}...")
                html_content = request_url(agent, prompt=prompt, page=1)
                
                if html_content:
                    extract_function = globals()[f"extract_jobs_{agent['name']}"]
                    extracted_jobs = extract_function(html_content, agent['name'])
                    all_jobs.extend(extracted_jobs)
                
                progress_bar.progress((i + 1) / len(selected_agents))

        if not all_jobs:
            st.warning("לא נמצאו משרות מתאימות")
            return

        status_text.text("יוצר קובץ Excel...")
        wb = create_excel_from_json(all_jobs)
        
        excel_file = io.BytesIO()
        wb.save(excel_file)
        excel_file.seek(0)

        b64 = base64.b64encode(excel_file.read()).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="רשימת_משרות.xlsx">לחץ כאן להורדת קובץ Excel</a>'
        st.markdown(href, unsafe_allow_html=True)

        status_text.text(f"נמצאו {len(all_jobs)} משרות בסך הכל.")
        progress_bar.progress(100)

        try:
            df = pd.DataFrame(all_jobs)
            st.write("תוצאות החיפוש:")
            st.dataframe(df)
        except Exception as e:
            st.error(f"אירעה שגיאה ביצירת טבלת הנתונים: {str(e)}")
            st.write("Debug: תוכן all_jobs:")
            st.write(all_jobs)

if __name__ == "__main__":
    main()