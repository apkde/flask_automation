from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
import os
from dotenv import load_dotenv
import tempfile
from datetime import datetime
import pyautogui
import time
import keyboard
import win32gui
import win32con
import pyperclip
import json

# Only load .env in development
if os.environ.get('FLASK_ENV') != 'production':
    load_dotenv()

# Debug API key loading
api_key = os.environ.get('GOOGLE_API_KEY')
print(f"API Key loaded: {api_key[:5]}...{api_key[-5:]}")

app = Flask(__name__)

# Configure Gemini API
if not api_key:
    raise ValueError("No API key found. Please set GOOGLE_API_KEY in your environment")

genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro')

def format_text(text, format_type='il'):
    try:
        prompt = f"""As a professional automation engineer, convert this English text into a precise Instruction List (IL) program for SoMachine Basic 1.4.
Follow these exact SoMachine Basic IL format rules:

1. Each network must start with (*NETWORKx*) where x is the number
2. Each network must have exactly ONE LD instruction
3. Available instructions: LD, AND, OR, ST only
4. For temperature comparison:
   - Use %MW0 for current temperature value
   - Use %M0.0 to %M0.7 for memory bits
   - Compare using AND/OR logic only
5. Variable naming:
   %I0.x - Input bits (0-7)
   %Q0.x - Output bits (0-7)
   %M0.x - Memory bits (x: 0-7)
   %MW0 - Current Temperature Value
   %MW1 - Temperature Setpoint Low (30)
   %MW2 - Temperature Setpoint High (80)

Example format:
(*NETWORK_1*)
(*Temperature Input*)
    LD %I0.0    (*Temperature Sensor*)
    ST %MW0     (*Store Temperature Value*)

(*NETWORK_2*)
(*Temperature Check*)
    LD %MW0     (*Current Temperature*)
    AND %M0.1   (*Temperature OK*)
    ST %M0.2    (*Temperature Status*)

Here's the automation sequence to implement: {text}

Remember: Use only LD, AND, OR, ST instructions. No CMP or other comparison instructions."""

        response = model.generate_content(prompt)
        return {
            'success': True,
            'result': response.text
        }
    except Exception as e:
        print(f"Full error details: {str(e)}")
        if "API_KEY_INVALID" in str(e):
            raise ValueError(f"Invalid API key. Error details: {str(e)}")
        raise e

def generate_export_file(code, plc_type):
    # Create temporary file with appropriate extension
    temp = tempfile.NamedTemporaryFile(delete=False, suffix='.smbp')
    
    # Convert IL code lines to proper XML format
    rungs = []
    current_rung = []
    line_number = 0
    
    for line in code.split('\n'):
        line = line.strip()
        if line:
            # Skip markdown code block markers
            if line.startswith('```') or line == '':
                continue
            
            # Start new rung on network header
            elif line.startswith('(*NETWORK'):
                # Start a new rung when we see a network header
                if current_rung:
                    rungs.append(current_rung)
                    current_rung = []
                line_number = 0
                current_rung.append(f"""              <InstructionLineEntity>
                <InstructionLine>{line}</InstructionLine>
                <LineNumber>{line_number:04d}</LineNumber>
                <Comment />
              </InstructionLineEntity>""")
                line_number += 1
            # Handle network description comments
            elif line.startswith('(*') and line.endswith('*)'):
                current_rung.append(f"""              <InstructionLineEntity>
                <InstructionLine>{line}</InstructionLine>
                <LineNumber>{line_number:04d}</LineNumber>
                <Comment>{line[2:-2].strip()}</Comment>
              </InstructionLineEntity>""")
                line_number += 1
            # Handle actual instructions
            else:
                # For instruction lines, extract comments between parentheses
                comment = ""
                if '(' in line and ')' in line:
                    parts = line.split('(')
                    line = parts[0].strip()
                    comment = parts[1].split(')')[0].strip()
                
                # Only add non-empty instruction lines
                if line:
                    current_rung.append(f"""              <InstructionLineEntity>
                <InstructionLine>{line}</InstructionLine>
                <LineNumber>{line_number:04d}</LineNumber>
                <Comment>{comment}</Comment>
              </InstructionLineEntity>""")
                    line_number += 1
    
    # Add the last rung if exists
    if current_rung:
        rungs.append(current_rung)
    
    # Generate XML for all rungs
    rungs_xml = []
    for rung_index, rung in enumerate(rungs):
        # Extract network description from first comment
        network_desc = ""
        if rung and '(*' in rung[0]:
            network_desc = rung[0].split('(*')[1].split('*)')[0].strip()
        
        rung_xml = f"""          <RungEntity>
            <LadderElements />
            <InstructionLines>
{chr(10).join(rung)}
            </InstructionLines>
            <Name>NETWORK_{rung_index + 1}</Name>
            <MainComment>{network_desc}</MainComment>
            <Label>Rung{rung_index}</Label>
            <IsLadderSelected>false</IsLadderSelected>
          </RungEntity>"""
        rungs_xml.append(rung_xml)
    
    all_rungs = chr(10).join(rungs_xml)
    
    # SoMachine Basic project structure
    project_content = f"""<?xml version="1.0" encoding="utf-8"?>
<ProjectDescriptor xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <ProjectVersion>1.7.0.0</ProjectVersion>
  <ManagementLevel>FunctLevelMan8_0</ManagementLevel>
  <Name>Generated_Project</Name>
  <SoftwareConfiguration>
    <Pous>
      <ProgramOrganizationUnits>
        <Name>Main</Name>
        <SectionNumber>0</SectionNumber>
        <Rungs>
{all_rungs}
        </Rungs>
      </ProgramOrganizationUnits>
    </Pous>
    <MemoryBitsMemoryAllocation>
      <Allocation>Manual</Allocation>
      <ForcedCount>512</ForcedCount>
    </MemoryBitsMemoryAllocation>
    <MemoryWordsMemoryAllocation>
      <Allocation>Manual</Allocation>
      <ForcedCount>2000</ForcedCount>
    </MemoryWordsMemoryAllocation>
  </SoftwareConfiguration>
  <HardwareConfiguration>
    <Plc>
      <Cpu>
        <Reference>TM100C16R</Reference>
        <Name>MyController</Name>
      </Cpu>
    </Plc>
  </HardwareConfiguration>
</ProjectDescriptor>"""
    
    with open(temp.name, 'w', encoding='utf-8') as f:
        f.write(project_content)
    
    return temp.name

def type_code_into_somachine(code):
    try:
        # Correct path for SoMachine Basic
        somachine_path = r"C:\Program Files (x86)\Schneider Electric\SoMachine Basic\SchneiderElectric.SoMachineBasic.MainApplication.exe"

        if not os.path.exists(somachine_path):
            return {
                "success": False, 
                "error": "SoMachine Basic not found at expected path. Please verify installation."
            }

        print(f"Found SoMachine Basic at: {somachine_path}")
        os.startfile(somachine_path)
        time.sleep(15)  # Wait for SoMachine Basic to fully load
        
        # Find SoMachine window
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if 'somachine' in window_title.lower():
                    windows.append((hwnd, window_title))
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)
        
        somachine_window = None
        for hwnd, title in windows:
            if 'somachine' in title.lower():
                somachine_window = hwnd
                print(f"Found SoMachine window: {title}")
                break
                
        if not somachine_window:
            return {"success": False, "error": "SoMachine Basic window not found"}

        try:
            # Maximize window
            win32gui.ShowWindow(somachine_window, win32con.SW_MAXIMIZE)
            time.sleep(1)
            
            # Create new project
            pyautogui.hotkey('ctrl', 'n')
            time.sleep(2)
            
            # Select TM100C16R controller
            pyautogui.write('tm100')  # Type to search
            time.sleep(0.5)
            pyautogui.press('enter')
            time.sleep(2)
            
            # Save project first
            pyautogui.hotkey('ctrl', 's')
            time.sleep(1)
            
            # Type project name with IL indication
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            project_name = f"TM100_IL_Project_{current_time}"
            pyperclip.copy(project_name)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            
            # Navigate to save location
            save_path = os.path.expanduser("~\\Documents\\SoMachine Basic")
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            
            pyperclip.copy(save_path)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            
            # Confirm save
            pyautogui.press('enter')
            time.sleep(2)
            
            # Now navigate to Programming
            pyautogui.press('alt')
            time.sleep(0.2)
            pyautogui.press('p')  # Programming menu
            time.sleep(0.5)
            
            # Add new section
            pyautogui.press(['down', 'down', 'right', 'enter'])  # Navigate to Add Section
            time.sleep(0.5)
            
            # Select IL
            pyautogui.write('il')
            time.sleep(0.2)
            pyautogui.press('enter')
            time.sleep(1)
            
            # Type the code with proper formatting
            lines = code.split('\n')
            for line in lines:
                if line.strip():
                    if '(*NETWORK' in line:
                        pyautogui.press('enter')  # Add blank line before network
                        pyperclip.copy(line)
                        pyautogui.hotkey('ctrl', 'v')
                        pyautogui.press('enter')
                    elif line.strip().startswith('(*') and line.strip().endswith('*)'):
                        pyperclip.copy(line)
                        pyautogui.hotkey('ctrl', 'v')
                        pyautogui.press('enter')
                    else:
                        pyperclip.copy(line)
                        pyautogui.hotkey('ctrl', 'v')
                        pyautogui.press('enter')
                    time.sleep(0.2)
            
            return {
                "success": True, 
                "message": f"TM100 IL Project saved as {project_name} in {save_path}"
            }
            
        except Exception as e:
            print(f"Automation error: {str(e)}")
            return {"success": False, "error": str(e)}
            
    except Exception as e:
        print(f"Error details: {str(e)}")
        return {"success": False, "error": str(e)}

@app.route('/')
def index():
    return render_template('index.html', show_splash=True)

@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json()
    text = data.get('text', '')
    format_type = data.get('format_type', 'il')  # Get the selected format
    
    try:
        result = format_text(text, format_type)  # Pass format type to format_text
        return jsonify(result)
    except Exception as e:
        print(f"Translation error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/export', methods=['POST'])
def export():
    data = request.get_json()
    code = data.get('code', '')
    plc_type = data.get('plc_type', 'somachine')
    
    try:
        file_path = generate_export_file(code, plc_type)
        return jsonify({
            'success': True, 
            'file_path': file_path,
            'filename': 'TM100_IL_Project.smbp'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/download/<path:filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

@app.route('/type_code', methods=['POST'])
def type_code():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        result = type_code_into_somachine(code)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/voice_command', methods=['POST'])
def voice_command():
    try:
        data = request.get_json()
        command = data.get('command', '')
        
        # Prompt for Gemini to understand voice commands
        prompt = f"""As an industrial automation assistant, interpret this voice command and respond appropriately:
"{command}"

Respond in JSON format:
{{
    "action": "generate|export|clear|other",
    "response": "Your friendly response to the user",
    "input_text": "Any text that should be added to input box (if applicable)"
}}

Example responses:
- For "create a program for temperature control": {{"action": "generate", "response": "I'll help you create a temperature control program", "input_text": "Create a temperature control system with..."}}
- For "export this to somachine": {{"action": "export", "response": "Exporting your program to SoMachine Basic", "input_text": ""}}
- For "clear everything": {{"action": "clear", "response": "Clearing all inputs and outputs", "input_text": ""}}"""

        response = model.generate_content(prompt)
        return jsonify(json.loads(response.text))
    except Exception as e:
        return jsonify({
            'error': str(e),
            'action': 'other',
            'response': 'Sorry, I had trouble understanding that command.'
        })

if __name__ == '__main__':
    app.run(debug=True) 