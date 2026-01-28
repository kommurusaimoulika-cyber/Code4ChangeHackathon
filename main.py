import os
import io
import sqlite3
import datetime
import json
import asyncio
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv() 
API_KEY = os.getenv("GOOGLE_API_KEY")

# --- EMERGENCY DEMO MODE ---
# Set this to True if AI keeps hanging. It will fake the result so you can record the video.
DEMO_MODE = False 

if not API_KEY and not DEMO_MODE:
    raise ValueError("No GOOGLE_API_KEY found")

if not DEMO_MODE:
    genai.configure(api_key=API_KEY)
    # Reverted to 1.5-flash for maximum speed/stability
    model = genai.GenerativeModel('gemini-2.5-flash')

app = FastAPI()

# --- CORS ---
origins = ["http://localhost:5500", "http://127.0.0.1:5500", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("backend/uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="backend/uploads"), name="static")

# --- DATABASE ---
def init_db():
    conn = sqlite3.connect('backend/watchwaste.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports 
                 (id INTEGER PRIMARY KEY, lat REAL, lon REAL, 
                  image_path TEXT, status TEXT, timestamp TEXT, 
                  ai_analysis TEXT, confidence REAL)''')
    conn.commit()
    conn.close()

init_db()

@app.post("/report")
async def report_waste(lat: float = Form(...), lon: float = Form(...), file: UploadFile = File(...)):
    # 1. Save Image
    file_location = f"backend/uploads/{file.filename}"
    image_data = await file.read()
    with open(file_location, "wb") as f:
        f.write(image_data)
    
    # 2. AI Analysis
    print(f"Analyzing image... (Demo Mode: {DEMO_MODE})")
    
    is_trash = False
    description = "Pending"
    confidence = 0.0

    if DEMO_MODE:
        # FAKE SUCCESS FOR VIDEO RECORDING
        await asyncio.sleep(2) # Fake delay
        is_trash = True
        confidence = 0.98
        description = "DEMO MODE: Verified pile of garbage containing plastic and debris."
    else:
        try:
            image = Image.open(io.BytesIO(image_data))
            prompt = """
            Analyze this image for civic issues. 
            Does this image contain illegal garbage dumping, litter, overflowing bins, or construction debris?
            Return ONLY a JSON response like this: {"is_trash": true, "confidence": 0.95, "description": "A pile of plastic bags..."}
            If clean, set is_trash to false.
            """
            
            # --- CRITICAL FIX: Use ASYNC call so it doesn't freeze ---
            response = await model.generate_content_async([prompt, image])
            
            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
            analysis = json.loads(cleaned_text)
            
            is_trash = analysis.get("is_trash", False)
            description = analysis.get("description", "No description")
            confidence = analysis.get("confidence", 0.85 if is_trash else 0.0)
            
        except Exception as e:
            print(f"❌ AI Error: {e}")
            # If AI fails, we reject it (unless you turn on Demo Mode)
            is_trash = False 
            description = f"AI Error: {str(e)}"
            confidence = 0.0

    # 3. Save to DB
    if is_trash:
        status = "Verified Hotspot"
        conn = sqlite3.connect('backend/watchwaste.db')
        c = conn.cursor()
        c.execute("INSERT INTO reports (lat, lon, image_path, status, timestamp, ai_analysis, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (lat, lon, file.filename, status, datetime.datetime.now(), description, confidence))
        conn.commit()
        conn.close()
        
        return {
            "status": "success", 
            "message": "Waste Verified!", 
            "details": description,
            "confidence": confidence
        }
    else:
        return {
            "status": "rejected", 
            "message": "Not identified as waste.", 
            "details": description,
            "confidence": confidence
        }

@app.get("/get-hotspots")
def get_hotspots():
    conn = sqlite3.connect('backend/watchwaste.db')
    c = conn.cursor()
    c.execute("SELECT lat, lon, status, image_path, timestamp, ai_analysis, confidence FROM reports")
    rows = c.fetchall()
    conn.close()
    data = []
    for r in rows:
        data.append({
            "lat": r[0], "lon": r[1], 
            "status": r[2], 
            "image": f"http://localhost:8000/static/{r[3]}", 
            "time": r[4],
            "analysis": r[5],
            "confidence": r[6]
        })
    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# import os
# import io
# import sqlite3
# import datetime
# import json
# from fastapi import FastAPI, UploadFile, File, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from PIL import Image
# import google.generativeai as genai
# from dotenv import load_dotenv

# # 1. Load Environment Variables
# load_dotenv() 
# API_KEY = os.getenv("GOOGLE_API_KEY")

# if not API_KEY:
#     raise ValueError("No GOOGLE_API_KEY found in .env file")

# genai.configure(api_key=API_KEY)
# # Using the stable model
# model = genai.GenerativeModel('gemini-2.5-flash')

# app = FastAPI()

# # --- CORS SETUP ---
# origins = [
#     "http://localhost:5500",
#     "http://127.0.0.1:5500",
#     "*"
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# os.makedirs("backend/uploads", exist_ok=True)
# app.mount("/static", StaticFiles(directory="backend/uploads"), name="static")

# # --- DATABASE SETUP ---
# def init_db():
#     conn = sqlite3.connect('backend/watchwaste.db')
#     c = conn.cursor()
#     # ensure table has 'confidence' column
#     c.execute('''CREATE TABLE IF NOT EXISTS reports 
#                  (id INTEGER PRIMARY KEY, lat REAL, lon REAL, 
#                   image_path TEXT, status TEXT, timestamp TEXT, 
#                   ai_analysis TEXT, confidence REAL)''')
#     conn.commit()
#     conn.close()

# init_db()

# @app.post("/report")
# async def report_waste(lat: float = Form(...), lon: float = Form(...), file: UploadFile = File(...)):
#     # 1. Save Image
#     file_location = f"backend/uploads/{file.filename}"
#     image_data = await file.read()
#     with open(file_location, "wb") as f:
#         f.write(image_data)
    
#     # 2. GenAI Analysis
#     print("Sending to Gemini AI...")
#     try:
#         image = Image.open(io.BytesIO(image_data))
        
#         prompt = """
#         Analyze this image for civic issues. 
#         Does this image contain illegal garbage dumping, litter, overflowing bins, or construction debris?
#         Return ONLY a JSON response like this: {"is_trash": true, "confidence": 0.95, "description": "A pile of plastic bags..."}
#         If clean, set is_trash to false.
#         """
        
#         response = model.generate_content([prompt, image])
        
#         # Parse JSON
#         cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
#         analysis = json.loads(cleaned_text)
        
#         is_trash = analysis.get("is_trash", False)
#         description = analysis.get("description", "No description")
#         # FIX: Extract confidence, default to 0.85 if missing but trash is found
#         confidence = analysis.get("confidence", 0.85 if is_trash else 0.0)
        
#     except Exception as e:
#         print(f"AI Error: {e}")
#         is_trash = False 
#         description = "AI Verification Failed"
#         confidence = 0.0

#     # 3. Save to DB
#     if is_trash:
#         status = "Verified Hotspot"
#         conn = sqlite3.connect('backend/watchwaste.db')
#         c = conn.cursor()
#         # FIX: Insert confidence value into DB
#         c.execute("INSERT INTO reports (lat, lon, image_path, status, timestamp, ai_analysis, confidence) VALUES (?, ?, ?, ?, ?, ?, ?)",
#                   (lat, lon, file.filename, status, datetime.datetime.now(), description, confidence))
#         conn.commit()
#         conn.close()
        
#         return {
#             "status": "success", 
#             "message": "Waste Verified by GenAI!", 
#             "details": description,
#             "confidence": confidence
#         }
#     else:
#         return {
#             "status": "rejected", 
#             "message": "AI did not detect waste.", 
#             "details": description,
#             "confidence": confidence
#         }

# @app.get("/get-hotspots")
# def get_hotspots():
#     conn = sqlite3.connect('backend/watchwaste.db')
#     c = conn.cursor()
#     # FIX: Select confidence column
#     c.execute("SELECT lat, lon, status, image_path, timestamp, ai_analysis, confidence FROM reports")
#     rows = c.fetchall()
#     conn.close()
    
#     data = []
#     for r in rows:
#         data.append({
#             "lat": r[0], "lon": r[1], 
#             "status": r[2], 
#             "image": f"http://localhost:8000/static/{r[3]}", 
#             "time": r[4],
#             "analysis": r[5],
#             "confidence": r[6] # Send confidence to frontend
#         })
#     return data

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)



# import os
# import io
# import sqlite3
# import datetime
# import json
# from fastapi import FastAPI, UploadFile, File, Form
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
# from PIL import Image
# import google.generativeai as genai
# from dotenv import load_dotenv 

# # 1. Load Environment Variables
# load_dotenv() 

# # 2. Get the Key
# API_KEY = os.getenv("GOOGLE_API_KEY")

# if not API_KEY:
#     raise ValueError("No GOOGLE_API_KEY found in .env file")

# genai.configure(api_key=API_KEY)

# # Use Gemini 1.5 Flash
# model = genai.GenerativeModel('gemini-2.5-flash')

# app = FastAPI()

# # Enable CORS
# # app.add_middleware(
# #     CORSMiddleware,
# #     allow_origins=["*"],
# #     allow_methods=["*"],
# #     allow_headers=["*"],
# # )
# # We explicitly list the frontend URL and allow everything
# origins = [
#     "http://localhost:5500",
#     "http://127.0.0.1:5500",
#     "*"  # Allow all for hackathon purposes
# ]
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# os.makedirs("backend/uploads", exist_ok=True)
# app.mount("/static", StaticFiles(directory="backend/uploads"), name="static")

# def init_db():
#     conn = sqlite3.connect('backend/watchwaste.db')
#     c = conn.cursor()
#     c.execute('''CREATE TABLE IF NOT EXISTS reports 
#                  (id INTEGER PRIMARY KEY, lat REAL, lon REAL, 
#                   image_path TEXT, status TEXT, timestamp TEXT, ai_analysis TEXT)''')
#     conn.commit()
#     conn.close()

# init_db()

# @app.post("/report")
# async def report_waste(lat: float = Form(...), lon: float = Form(...), file: UploadFile = File(...)):
#     # 1. Save Image
#     file_location = f"backend/uploads/{file.filename}"
#     image_data = await file.read()
#     with open(file_location, "wb") as f:
#         f.write(image_data)
    
#     # 2. GenAI Analysis
#     print("Sending to Gemini AI...")
#     try:
#         image = Image.open(io.BytesIO(image_data))
        
#         # The Magic Prompt
#         prompt = """
#         Analyze this image for civic issues. 
#         Does this image contain illegal garbage dumping, litter, overflowing bins, or construction debris?
#         Return ONLY a JSON response like this: {"is_trash": true, "confidence": 0.95, "description": "A pile of plastic bags and cardboard on the street."}
#         If it is clean or irrelevant, set is_trash to false.
#         """
        
#         response = model.generate_content([prompt, image])
        
#         # Clean response to get pure JSON
#         cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
#         analysis = json.loads(cleaned_text)
        
#         is_trash = analysis.get("is_trash", False)
#         description = analysis.get("description", "No description")
        
#     except Exception as e:
#         print(f"AI Error: {e}")
#         # Fallback if AI fails (e.g. internet issue)
#         is_trash = False 
#         description = "AI Verification Failed"

#     # 3. Handle Result
#     if is_trash:
#         status = "Verified Hotspot"
#         conn = sqlite3.connect('backend/watchwaste.db')
#         c = conn.cursor()
#         c.execute("INSERT INTO reports (lat, lon, image_path, status, timestamp, ai_analysis) VALUES (?, ?, ?, ?, ?, ?)",
#                   (lat, lon, file.filename, status, datetime.datetime.now(), description))
#         conn.commit()
#         conn.close()
#         return {
#             "status": "success", 
#             "message": "Waste Verified by Multi-Modal Vision Generative AI!", 
#             "details": description
#         }
#     else:
#         # os.remove(file_location) # Optional cleanup
#         return {
#             "status": "rejected", 
#             "message": "AI did not detect waste. Please try again.", 
#             "details": description
#         }

# @app.get("/get-hotspots")
# def get_hotspots():
#     conn = sqlite3.connect('backend/watchwaste.db')
#     c = conn.cursor()
#     c.execute("SELECT lat, lon, status, image_path, timestamp, ai_analysis FROM reports")
#     rows = c.fetchall()
#     conn.close()
    
#     data = []
#     for r in rows:
#         data.append({
#             "lat": r[0], "lon": r[1], 
#             "status": r[2], 
#             "image": f"http://localhost:8000/static/{r[3]}", 
#             "time": r[4],
#             "analysis": r[5]
#         })
#     return data

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)