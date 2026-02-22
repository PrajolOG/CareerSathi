import os
from google import genai
from google.genai import types
from supabase import create_client, ClientOptions
from app.database import supabase as global_supabase, url, key

class ChatService:
    def __init__(self):
        # 1. Setup Gemini Client
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 2. Load System Prompt
        self.system_prompt = "You are a helpful career counselor."
        try:
            prompt_path = os.path.join("app", "prompts", "system_prompt.txt")
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except Exception:
            print("System prompt file not found, using default.")

        # 3. Model Names
        self.primary_model_name = 'gemini-flash-latest'
        self.backup_model_name = 'gemini-3-flash-preview'

    async def get_career_advice(self, user_message: str, user_token: str) -> str:
        """Non-streaming version for backward compatibility or simple calls."""
        full_text = ""
        async for chunk in self.stream_career_advice(user_message, user_token):
            full_text += chunk
        return full_text

    async def stream_career_advice(self, user_message: str, user_token: str):
        """
        1. Validate Token
        2. Create Authenticated DB Connection (for RLS)
        3. Build Context
        4. Stream AI Response
        5. Save History after completion
        """
        
        # --- Authentication ---
        user_id = None
        db_client = None

        try:
            user_response = global_supabase.auth.get_user(user_token)
            if not user_response or not user_response.user:
                yield "Authentication failed. Please login again."
                return
            
            user_id = user_response.user.id
            db_client = create_client(
                url, 
                key, 
                options=ClientOptions(headers={"Authorization": f"Bearer {user_token}"})
            )

        except Exception as e:
            print(f"Auth Error in Service: {str(e)}")
            yield "Authentication failed. Please login again."
            return

        # --- Context Building ---
        chat_history = self._build_history(db_client, user_id)
        
        # --- AI Generation (Streaming) ---
        ai_response_text = ""
        config = types.GenerateContentConfig(
            system_instruction=self.system_prompt,
        )
        
        try:
            # Try Primary
            response_stream = self.client.models.generate_content_stream(
                model=self.primary_model_name,
                contents=chat_history + [types.Content(role="user", parts=[types.Part(text=user_message)])],
                config=config
            )
            for chunk in response_stream:
                if chunk.text:
                    ai_response_text += chunk.text
                    yield chunk.text
            
        except Exception as e:
            print(f"Primary model failed: {e}. Switching to Backup.")
            try:
                # Try Backup
                response_stream = self.client.models.generate_content_stream(
                    model=self.backup_model_name,
                    contents=chat_history + [types.Content(role="user", parts=[types.Part(text=user_message)])],
                    config=config
                )
                for chunk in response_stream:
                    if chunk.text:
                        ai_response_text += chunk.text
                        yield chunk.text
            except Exception as e2:
                print(f"Backup model failed: {e2}")
                yield "I am currently overloaded. Please try again later."
                return

        # --- Save to Database (background) ---
        if ai_response_text:
            self._save_to_db(db_client, user_id, "user", user_message)
            self._save_to_db(db_client, user_id, "ai", ai_response_text)

    def _build_history(self, client, user_id: str):
        """Fetches Profile + Last 20 messages using the authenticated client."""
        formatted_history = []

        try:
            # 1. Fetch Profile (Respects RLS: Users can only see their own)
            profile = client.table("Profiles").select("*").eq("id", user_id).single().execute()
            data = profile.data
            
            context_msg = (
                f"CONTEXT: User: {data.get('full_name')}. "
                f"Grade: {data.get('grade_level')}. "
                f"Gender: {data.get('gender')}."
            )
            
            formatted_history.append(types.Content(role="user", parts=[types.Part(text=context_msg)]))
            formatted_history.append(types.Content(role="model", parts=[types.Part(text="Understood. I have the context.")]))
            
        except Exception as e:
            print(f"Profile Fetch Error: {e}")
            # Continue without profile if it fails

        try:
            # 2. Fetch Chat History
            rows = client.table("Chat_History")\
                .select("*")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .limit(20)\
                .execute()
            
            # Reverse to chronological order
            past_messages = rows.data[::-1]

            for msg in past_messages:
                role = "user" if msg['sender'] == "user" else "model"
                formatted_history.append(types.Content(role=role, parts=[types.Part(text=msg['message'])]))
                
        except Exception as e:
            print(f"History Fetch Error: {e}")

        return formatted_history

    def _save_to_db(self, client, user_id: str, sender: str, text: str):
        try:
            client.table("Chat_History").insert({
                "user_id": user_id,
                "sender": sender,
                "message": text
            }).execute()
        except Exception as e:
            print(f"Save DB Error: {e}")
