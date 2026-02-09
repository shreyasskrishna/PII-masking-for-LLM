"""
Streamlit Chat UI for Privacy-Preserving Customer Support AI

Run with: streamlit run app.py
"""

import streamlit as st
import re
import os
from typing import Dict, Tuple
from dotenv import load_dotenv
import requests

load_dotenv()

# ============================================================================
# PII MASKING ENGINE
# ============================================================================

class PIIMasker:
    def __init__(self):
        self.patterns = {
            "EMAIL": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "PHONE": r'\b(\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
            "SSN": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            "CC": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            "IP": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
        }
        self.current_mapping: Dict[str, str] = {}
        self.reverse_mapping: Dict[str, str] = {}
    
    def mask(self, text: str) -> Tuple[str, Dict[str, str]]:
        self.current_mapping = {}
        self.reverse_mapping = {}
        masked_text = text
        
        for pii_type, pattern in self.patterns.items():
            matches = list(re.finditer(pattern, masked_text))
            for i, match in enumerate(reversed(matches)):
                original_value = match.group(0)
                if original_value in self.reverse_mapping:
                    token = self.reverse_mapping[original_value]
                else:
                    token = f"<{pii_type}_{len([k for k in self.current_mapping if k.startswith(f'<{pii_type}_')]) + 1}>"
                    self.current_mapping[token] = original_value
                    self.reverse_mapping[original_value] = token
                start, end = match.span()
                masked_text = masked_text[:start] + token + masked_text[end:]
        
        return masked_text, self.current_mapping.copy()
    
    def unmask(self, text: str, mapping: Dict[str, str]) -> str:
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result

# ============================================================================
# GROQ CLIENT
# ============================================================================

SYSTEM_PROMPT = """You are a helpful Customer Support AI. All user PII is masked with tokens like <EMAIL_1>, <PHONE_1>.
Rules: Use tokens exactly as shown, never reveal real values, be professional and helpful."""

class GroqClient:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
    
    def chat(self, messages: list) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        try:
            response = requests.post(self.base_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"Error: {str(e)}"

# ============================================================================
# STREAMLIT APP
# ============================================================================

st.set_page_config(
    page_title="Privacy-Preserving Customer Support",
    page_icon="🔐",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    .main-header {
        text-align: center;
        padding: 1rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .main-header h1 {
        color: white;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: #e0e0e0;
        margin: 0.5rem 0 0 0;
    }
    .mapping-box {
        background: #2d2d44;
        border-radius: 8px;
        padding: 1rem;
        margin-top: 1rem;
    }
    .mapping-item {
        background: #3d3d5c;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        margin: 0.3rem 0;
        font-family: monospace;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background: #4a4a6a;
        margin-left: 2rem;
    }
    .bot-message {
        background: #2d4a5e;
        margin-right: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>🔐 Privacy-Preserving Customer Support AI</h1>
    <p>Your PII is masked before being sent to the AI</p>
</div>
""", unsafe_allow_html=True)

# Get API key from .env
api_key = os.getenv("GROQ_API_KEY", "")

# Sidebar
with st.sidebar:
    st.header("📁 PII Mapping")
    if "pii_mapping" in st.session_state and st.session_state.pii_mapping:
        for token, value in st.session_state.pii_mapping.items():
            st.code(f"{token} → {value}")
    else:
        st.info("No PII detected yet")
    
    st.divider()
    
    if st.button("🔄 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pii_mapping = {}
        st.session_state.chat_history = []
        st.session_state.msg_visibility = {}
        st.rerun()
    
    st.divider()
    st.caption("💡 Try: 'My email is test@gmail.com and phone is 555-123-4567'")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pii_mapping" not in st.session_state:
    st.session_state.pii_mapping = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

masker = PIIMasker()

if "msg_visibility" not in st.session_state:
    st.session_state.msg_visibility = {}

# Display chat messages
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🤖"):
        if msg["role"] == "assistant":
            # Default to hidden (False) if not in state
            if i not in st.session_state.msg_visibility:
                st.session_state.msg_visibility[i] = False
            
            if st.session_state.msg_visibility[i]:
                st.markdown(msg["content"])
                label = "👁️ Hide Content"
            else:
                # Display the masked content (with placeholders) instead of asterisks
                # Fallback to asterisks if masked_content is missing (for old messages)
                masked_disp = msg.get("masked_content", "*" * len(msg["content"]))
                
                # Use code block or text for masked content to make it distinct
                st.markdown(masked_disp) 
                label = "🙈 Show Content"
            
            if st.button(label, key=f"toggle_{i}"):
                st.session_state.msg_visibility[i] = not st.session_state.msg_visibility[i]
                st.rerun()
        else:
            # User messages
            # For user messages, we can also support toggling if we want, but currently 
            # the requirement mostly implied the "response and display". 
            # However, looking at the previous code, user messages were just shown. 
            # The prompt says: "display in hide content , while hiding the content i only need to hide the maked details... and while displaying the hide contents like to display the other texts."
            # The previous code only had toggle logic for "assistant" (lines 198-214).
            # But wait, looking at the user request: "there is an correction in the response and display in hide content". 
            # It seems they want this behavior generally. 
            # Currently the code calculates masking for user input immediately.
            
            # Let's apply the same logic to User messages if we want them to be toggle-able?
            # The original code only had the toggle for assistant.
            # "if msg['role'] == 'assistant': ... else: st.markdown(msg['content'])"
            # I will stick to the existing pattern of only toggling Assistant responses for now, 
            # BUT the user also said "while displaying the hide contents like to display the other texts".
            # This implies they want to read the text SURROUNDING the PII.
            # The user's request seems to apply to the *content that is hidden*. 
            # In the current app, the Assistant response IS hidden by default. 
            # The User message is NOT hidden by default (it's just shown).
            # So I will focus on the Assistant message for the toggle.
            
            # However, for consistency, if the user message HAS PII, we might want to show the masked version?
            # The original code shows the raw prompt in line 224: st.markdown(prompt).
            # And then shows "PII Masked" expander below it (lines 233).
            # I will leave the User message display as is (raw), because the user sees what they typed.
            # The focus is clearly on the "Hide Content" feature which currently only exists for Assistant.
            st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Type your message (include emails, phones to see masking)..."):
    if not api_key:
        st.error("Please enter your Groq API key in the sidebar")
    else:
        # Display user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
        
        # We'll append to messages later after we calculate the masked version, 
        # so we can store both. Or we can just calculate it now.
        # The original code masked it at line 228. Let's move that up or just do it.
        # Actually, line 228 is: masked_input, new_mapping = masker.mask(prompt)
        # So I need to use masked_input.

        
        # Mask PII
        masked_input, new_mapping = masker.mask(prompt)
        
        # Store user message with masked version
        st.session_state.messages.append({
            "role": "user", 
            "content": prompt,
            "masked_content": masked_input
        })
        st.session_state.pii_mapping.update(new_mapping)
        
        # Show masking info
        if new_mapping:
            with st.expander("🔒 PII Masked", expanded=False):
                st.code(masked_input)
                for token, value in new_mapping.items():
                    st.caption(f"{token} ← {value}")
        
        # Add to chat history for context
        st.session_state.chat_history.append({"role": "user", "content": masked_input})
        
        # Get LLM response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                client = GroqClient(api_key)
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + st.session_state.chat_history
                masked_response = client.chat(messages)
                
                # Unmask response
                final_response = masker.unmask(masked_response, st.session_state.pii_mapping)
                st.text("*" * len(final_response))
        
        # Store messages
        st.session_state.chat_history.append({"role": "assistant", "content": masked_response})
        st.session_state.messages.append({
            "role": "assistant", 
            "content": final_response,
            "masked_content": masked_response
        })
        
        st.rerun()
