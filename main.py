import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def create_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # שימוש בדרייבר המותקן במערכת
    service = Service('/usr/bin/chromedriver')
    
    return webdriver.Chrome(service=service, options=chrome_options)

# שאר הקוד נשאר ללא שינוי
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

# טעינת הסוכנים מקובץ JSON
with open('agents.json', 'r', encoding='utf-8') as file:
    agents = json.load(file)

def request_url(agent, prompt, page=1):
    driver = create_driver()
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