"""
Privacy-Preserving Customer Support AI Bot with Groq LLM Integration

This module implements a complete PII masking pipeline for AI customer support:
User Input → Mask PII → Send to LLM → Get Response → Unmask PII → Return to User

Author: Customer Support AI Team
Date: February 2026
"""

import re
import os
from typing import Dict, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# PII MASKING ENGINE
# ============================================================================

class PIIMasker:
    """
    Handles detection, masking, and unmasking of Personally Identifiable Information.
    Uses regex-based pattern matching with token-based replacement.
    """
    
    def __init__(self):
        # Define regex patterns for different PII types
        self.patterns = {
            "EMAIL": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "PHONE": r'\b(\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
            "SSN": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            "CC": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            "IP": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',
            "USER_ID": r'\b[A-Z]{2,4}[-_]?\d{6,10}\b',
            "ACCOUNT": r'\b\d{10,16}\b'
        }
        
        # Storage for current session mappings
        self.current_mapping: Dict[str, str] = {}
        self.reverse_mapping: Dict[str, str] = {}
    
    def mask(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Mask all PII in the input text.
        """
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
        """
        Restore original PII values in the text.
        """
        result = text
        for token, original in mapping.items():
            result = result.replace(token, original)
        return result


# ============================================================================
# SYSTEM PROMPT FOR LLM
# ============================================================================

SYSTEM_PROMPT = """You are a Customer Support AI Assistant operating in a privacy-preserving environment.

CRITICAL CONTEXT:
All sensitive user information such as emails, phone numbers, credit card numbers, account IDs, and personal identifiers are automatically masked before reaching you.

Masked data appears in this format:
<EMAIL_1>, <PHONE_1>, <CC_1>, <USER_ID_1>, etc.

These tokens represent real user data but you must NEVER attempt to infer, reconstruct, modify, or request the original values.

SECURITY & COMPLIANCE RULES (MANDATORY):
- Never ask for or display real personal data
- Never guess or fabricate PII values
- Never alter token format or numbering
- Never remove or merge tokens
- Always reuse tokens exactly as shown in the user message
- Do not generate new tokens unless present in the input

RESPONSE STYLE:
- Professional, friendly, and empathetic
- Clear and action-oriented
- Provide helpful solutions and next steps
- Confirm actions taken
- Ask clarifying questions when needed (but never ask for PII)

Remember: You are having a real conversation. Respond naturally and helpfully to each message.
Your goal is to provide accurate, helpful customer support while preserving complete data privacy."""


# ============================================================================
# GROQ LLM CLIENT
# ============================================================================

class GroqClient:
    """
    Client for Groq API to get real LLM responses.
    """
    
    def __init__(self, api_key: str = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.conversation_history = []
        
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found. Set it in .env file or pass directly.")
    
    def chat(self, user_message: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """
        Send message to Groq and get response.
        """
        import requests
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        # Build messages with system prompt
        messages = [{"role": "system", "content": system_prompt}] + self.conversation_history
        
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
            
            assistant_message = response.json()["choices"][0]["message"]["content"]
            
            # Add assistant response to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })
            
            return assistant_message
            
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Groq API: {str(e)}"
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []


# ============================================================================
# CUSTOMER SUPPORT BOT
# ============================================================================

class CustomerSupportBot:
    """
    Privacy-preserving customer support bot that integrates PII masking
    with Groq LLM for real responses.
    """
    
    def __init__(self, use_groq: bool = True):
        self.masker = PIIMasker()
        self.use_groq = use_groq
        self.groq_client = None
        self.conversation_history = []
        self.session_mapping: Dict[str, str] = {}
        
        if use_groq:
            try:
                self.groq_client = GroqClient()
            except ValueError as e:
                print(f"⚠️  {e}")
                print("Falling back to simulated responses.\n")
                self.use_groq = False
    
    def _call_llm(self, masked_message: str) -> str:
        """
        Send masked message to LLM and get response.
        """
        if self.use_groq and self.groq_client:
            return self.groq_client.chat(masked_message)
        else:
            # Fallback simulated responses
            return self._simulated_response(masked_message)
    
    def _simulated_response(self, masked_message: str) -> str:
        """Simulated LLM responses for demo when no API key."""
        simulated_responses = {
            "account": "I understand you're having trouble accessing your account. I've initiated a password reset and sent a verification link to <EMAIL_1>. Please also verify your identity using <PHONE_1>. Is there anything else I can help you with?",
            "payment": "I can see the payment issue. I've flagged the transaction on card ending in <CC_1> for review. Our billing team will contact you at <EMAIL_1> within 24 hours.",
            "default": "Thank you for contacting support. I've noted your concern and will ensure our team follows up at your registered contact details. Is there anything specific you'd like me to address?"
        }
        
        message_lower = masked_message.lower()
        if "account" in message_lower or "login" in message_lower or "access" in message_lower:
            return simulated_responses["account"]
        elif "payment" in message_lower or "card" in message_lower or "charge" in message_lower:
            return simulated_responses["payment"]
        else:
            return simulated_responses["default"]
    
    def process_message(self, user_input: str) -> Dict:
        """
        Complete privacy-preserving message processing pipeline.
        
        Pipeline: User Input → Mask PII → Send to LLM → Get Response → Unmask PII → Return to User
        """
        # Step 1: Mask PII in user input
        masked_input, mapping = self.masker.mask(user_input)
        
        # Update session mapping
        self.session_mapping.update(mapping)
        
        # Step 2 & 3: Send to LLM and get response
        masked_response = self._call_llm(masked_input)
        
        # Step 4: Unmask PII in response
        final_response = self.masker.unmask(masked_response, self.session_mapping)
        
        # Store in conversation history
        self.conversation_history.append({
            "user_raw": user_input,
            "user_masked": masked_input,
            "bot_masked": masked_response,
            "bot_final": final_response
        })
        
        return {
            "stages": {
                "1_user_input_raw": user_input,
                "2_masked_before_llm": masked_input,
                "3_mapping_store": self.session_mapping.copy(),
                "4_llm_response_masked": masked_response,
                "5_final_output_to_user": final_response
            },
            "response": final_response
        }
    
    def get_mapping(self) -> Dict[str, str]:
        """Return current session's PII mapping."""
        return self.session_mapping.copy()
    
    def clear_session(self):
        """Clear conversation history and mappings."""
        self.conversation_history = []
        self.session_mapping = {}
        if self.groq_client:
            self.groq_client.clear_history()


# ============================================================================
# DEMO / INTERACTIVE MODE
# ============================================================================

def print_stage(title: str, content: str, emoji: str = "📋"):
    """Pretty print a pipeline stage."""
    print(f"\n{emoji} {title}")
    print("─" * 50)
    print(content)


def run_demo():
    """Run a demonstration with a single example."""
    
    print("=" * 60)
    print("🔐 PRIVACY-PRESERVING CUSTOMER SUPPORT AI - DEMO")
    print("=" * 60)
    print("\nThis demo shows how PII is protected when interacting with AI.\n")
    
    bot = CustomerSupportBot(use_groq=False)  # Use simulated for demo
    
    message = "Hi, my email is demo.user@gmail.com and my phone number is (555) 123-4567. I can't log into my account."
    
    print("=" * 60)
    print("🎯 EXAMPLE: Account Recovery Request")
    print("=" * 60)
    
    result = bot.process_message(message)
    stages = result["stages"]
    
    print_stage("User Input (RAW)", stages["1_user_input_raw"], "👤")
    print_stage("Masked Before LLM", stages["2_masked_before_llm"], "🔒")
    
    mapping_str = "\n".join([f"  {k} → {v}" for k, v in stages["3_mapping_store"].items()])
    print_stage("Mapping Store", mapping_str, "📁")
    
    print_stage("LLM Response (masked)", stages["4_llm_response_masked"], "🤖")
    print_stage("Final Output to User", stages["5_final_output_to_user"], "✅")
    
    print("\n" + "=" * 60)
    print("✨ Demo complete! PII was protected throughout the pipeline.")
    print("=" * 60)


def interactive_mode():
    """Run an interactive customer support session with Groq LLM."""
    
    print("=" * 60)
    print("🔐 INTERACTIVE CUSTOMER SUPPORT (Groq LLM)")
    print("=" * 60)
    print("\nType your message (include emails, phones, etc.)")
    print("Commands: 'quit' to exit, 'show' to see PII mapping, 'clear' to reset\n")
    
    bot = CustomerSupportBot(use_groq=True)
    
    if bot.use_groq:
        print("✅ Connected to Groq API - Real LLM responses enabled!\n")
    else:
        print("⚠️  Using simulated responses (set GROQ_API_KEY for real LLM)\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if user_input.lower() == 'quit':
                print("\nThank you for using our support service. Goodbye! 👋")
                break
            elif user_input.lower() == 'show':
                print("\n📁 Current PII Mapping:")
                mapping = bot.get_mapping()
                if mapping:
                    for token, value in mapping.items():
                        print(f"   {token} → {value}")
                else:
                    print("   (No PII detected yet)")
                print()
                continue
            elif user_input.lower() == 'clear':
                bot.clear_session()
                print("\n🔄 Session cleared. Starting fresh!\n")
                continue
            elif not user_input:
                continue
            
            result = bot.process_message(user_input)
            print(f"\n🤖 Bot: {result['response']}\n")
            
        except KeyboardInterrupt:
            print("\n\nSession ended. Goodbye! 👋")
            break


def quick_test():
    """Run a single quick test."""
    print("\n🔐 Quick Test\n")
    
    bot = CustomerSupportBot(use_groq=True)
    test_msg = "Hi, my email is test@example.com and phone is (555) 123-4567. I need help with my order."
    
    print(f"Input: {test_msg}")
    result = bot.process_message(test_msg)
    print(f"\nMasked: {result['stages']['2_masked_before_llm']}")
    print(f"\nBot Response: {result['response']}")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n🔐 Privacy-Preserving Customer Support AI\n")
    print("Choose mode:")
    print("  1. Run Demo (see example pipeline - no API needed)")
    print("  2. Interactive Mode (chat with Groq LLM)")
    print("  3. Quick Test (single message test)")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        run_demo()
    elif choice == "2":
        interactive_mode()
    elif choice == "3":
        quick_test()
    else:
        print("Invalid choice. Running demo...")
        run_demo()
