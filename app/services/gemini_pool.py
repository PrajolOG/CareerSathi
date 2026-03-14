import os
import time
import asyncio
import itertools
from typing import Optional, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class GeminiPool:
    def __init__(self):
        # 1. Initialize the 5 keys from environment
        self.keys = [
            os.getenv(f"GEMINI_KEY_{i}") for i in range(1, 6)
        ]
        # Filter out None and placeholder strings
        self.keys = [k for k in self.keys if k and not k.startswith("REPLACE_WITH")]
        
        if not self.keys:
            raise ValueError("No valid Gemini API keys found in .env. Please provide at least one valid key in GEMINI_KEY_1 through GEMINI_KEY_5.")

        # 2. Setup the infinite cycle
        self.key_cycle = itertools.cycle(self.keys)
        
        # 3. Define models
        self.primary_model = "gemini-3.1-flash-lite-preview"
        self.backup_model = "gemini-3-flash-preview"

    def _get_client(self, api_key: str):
        """Create a new GenAI client for a specific key."""
        return genai.Client(api_key=api_key)

    async def generate_content(self, prompt: str, system_instruction: Optional[str] = None):
        """
        Nested Fallback Logic:
        - Primary Attempt: Try Primary Model with Current Key.
        - Internal Fallback: If 429, try Backup Model with same Key.
        - External Rotation: If both fail, move to Next Key and repeat.
        - Infinite Loop: Cycle through all keys.
        - Exponential Backoff: If all keys are exhausted.
        """
        backoff_factor = 2
        max_attempts = len(self.keys) * 3 # Allow a few full cycles if needed, or stick to one full pass
        
        # We'll try up to 3 full cycles before giving up or sleeping longer
        for cycle_attempt in range(3):
            for _ in range(len(self.keys)):
                current_key = next(self.key_cycle)
                client = self._get_client(current_key)
                
                # --- Step 1: Primary Attempt (Primary Model) ---
                try:
                    print(f"[GeminiPool] Attempting Primary Model with Key: {current_key[:8]}...")
                    response = await client.aio.models.generate_content(
                        model=self.primary_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction
                        ) if system_instruction else None
                    )
                    return response
                except Exception as e:
                    if "429" in str(e):
                        print(f"[GeminiPool] Primary Model Rate Limited (429) on Key: {current_key[:8]}...")
                        
                        # --- Step 2: Internal Fallback (Backup Model) ---
                        try:
                            print(f"[GeminiPool] Falling back to Backup Model with Key: {current_key[:8]}...")
                            response = await client.aio.models.generate_content(
                                model=self.backup_model,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_instruction
                                ) if system_instruction else None
                            )
                            return response
                        except Exception as e2:
                            if "429" in str(e2):
                                print(f"[GeminiPool] Backup Model also Rate Limited on Key: {current_key[:8]}...")
                            else:
                                print(f"[GeminiPool] Backup Model failed with non-429 error: {e2}")
                                # If it's not a rate limit, we might want to still rotate or raise
                    else:
                        print(f"[GeminiPool] Primary Model failed with non-429 error: {e}")
                
                # --- Step 3: External Rotation (Move to next key in loop) ---
                print(f"[GeminiPool] Rotating to next API key...")

            # If we finished a full pass of all keys and still hitting 429s
            wait_time = backoff_factor ** (cycle_attempt + 1)
            print(f"[GeminiPool] All keys exhausted/limited. Applying backoff: {wait_time}s...")
            await asyncio.sleep(wait_time)

        raise Exception("GeminiPool: All attempts exhausted across all keys after rotation and backoff.")

    async def generate_content_stream(self, prompt: str, system_instruction: Optional[str] = None):
        """
        Streaming version of the rotation logic.
        """
        backoff_factor = 2
        for cycle_attempt in range(3):
            for _ in range(len(self.keys)):
                current_key = next(self.key_cycle)
                client = self._get_client(current_key)
                
                # --- Step 1: Primary Attempt ---
                try:
                    print(f"[GeminiPool] Streaming Primary Model with Key: {current_key[:8]}...")
                    # Note: We need to consume the first chunk to see if it hits a 429 immediately
                    stream = await client.aio.models.generate_content_stream(
                        model=self.primary_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction
                        ) if system_instruction else None
                    )
                    # We'll try to yield from it
                    async for chunk in stream:
                        yield chunk
                    return # Success
                except Exception as e:
                    if "429" in str(e):
                        print(f"[GeminiPool] Primary Stream Rate Limited (429) on Key: {current_key[:8]}...")
                        
                        # --- Step 2: Internal Fallback ---
                        try:
                            print(f"[GeminiPool] Falling back to Backup Stream with Key: {current_key[:8]}...")
                            stream = await client.aio.models.generate_content_stream(
                                model=self.backup_model,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    system_instruction=system_instruction
                                ) if system_instruction else None
                            )
                            async for chunk in stream:
                                yield chunk
                            return # Success
                        except Exception as e2:
                            if "429" in str(e2):
                                print(f"[GeminiPool] Backup Stream also Rate Limited on Key: {current_key[:8]}...")
                            else:
                                print(f"[GeminiPool] Backup Stream failed: {e2}")
                    else:
                        print(f"[GeminiPool] Primary Stream failed: {e}")
                
            # --- Step 3: Rotation and Backoff ---
            wait_time = backoff_factor ** (cycle_attempt + 1)
            await asyncio.sleep(wait_time)

        raise Exception("GeminiPool: All streaming attempts exhausted across all keys.")

# Singleton instance
gemini_pool = GeminiPool()
