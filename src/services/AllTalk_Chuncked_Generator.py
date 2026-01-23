"""
AllTalk TTS Chunked Generator
Replicates the chunking logic from tts_generator.html for Python scripts
"""

import re
import requests
from typing import List, Optional
from pathlib import Path


class AllTalkChunkedTTS:
    """Generate TTS with automatic text chunking for long texts."""
    
    def __init__(self, api_base: str = "http://127.0.0.1:7851"):
        """
        Initialize the chunked TTS generator.
        
        Args:
            api_base: Base URL for AllTalk API (default: http://127.0.0.1:7851)
        """
        self.api_base = api_base.rstrip('/')
        self.api_endpoint = f"{self.api_base}/api/tts-generate"
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text (matches tts_generator.html logic).
        
        Args:
            text: Raw input text
            
        Returns:
            Cleaned text ready for TTS
        """
        # Replace special dashes and hyphens
        cleaned = re.sub(r' \- | \– ', ' ', text)
        
        # Replace percent signs
        cleaned = cleaned.replace('%', ' percent')
        
        # Fix period-quote spacing
        cleaned = re.sub(r'\.\s\'', ".'", cleaned)
        
        # Remove standalone brackets with quotes
        cleaned = re.sub(r'(?<!\w)[\']+(?!\w)', '', cleaned)
        
        # Replace double quotes with single quotes
        cleaned = cleaned.replace('"', "'")
        
        # Remove unwanted characters (keep letters, numbers, punctuation, and various language characters)
        pattern = r'[^a-zA-Z0-9\s.,;:!?\-\'"$À-ÿ\u00C0-\u017F\u0400-\u04FF\u0150\u0151\u0170\u0171\u0900-\u097F\u2018\u2019\u201C\u201D\u2026\u3001\u3002\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF\uAC00-\uD7A3\u1100-\u11FF\u3130-\u318F\uFF01\uFF0c\uFF1A\uFF1B\uFF1F\u011E\u011F\u0130\u0131\u015E\u015F\u00E7\u00C7\u00F6\u00D6]'
        cleaned = re.sub(pattern, '', cleaned)
        
        # Replace dash-space and double dashes with semicolon
        cleaned = re.sub(r'-\s', '; ', cleaned)
        cleaned = cleaned.replace('--', '; ')
        
        return cleaned
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences (matches tts_generator.html logic).
        
        Args:
            text: Cleaned text
            
        Returns:
            List of sentences
        """
        # Split by sentence-ending punctuation followed by space, or CJK punctuation
        # Matches: . ! ? : followed by optional quotes and space, or CJK punctuation
        pattern = r'(?<=[\[.!?:\]][\'"\u2018\u2019\u201C\u201D]*)\s+|(?<=[\u3002\uFF01\uFF1A\uFF1F])'
        sentences = re.split(pattern, text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        return sentences
    
    def create_chunks(self, sentences: List[str], chunk_size: int = 2) -> List[str]:
        """
        Group sentences into chunks.
        
        Args:
            sentences: List of sentences
            chunk_size: Number of sentences per chunk (default: 2)
            
        Returns:
            List of text chunks
        """
        chunks = []
        for i in range(0, len(sentences), chunk_size):
            chunk = ' '.join(sentences[i:i + chunk_size])
            chunks.append(chunk)
        
        return chunks
    
    def generate_chunk(
        self,
        text: str,
        character_voice: str,
        language: str = "en",
        output_file_name: str = "output",
        rvc_voice: str = "Disabled",
        rvc_pitch: float = 0,
        **kwargs
    ) -> dict:
        """
        Generate TTS for a single chunk.
        
        Args:
            text: Text to generate
            character_voice: Voice to use (e.g., "female_01.wav")
            language: Language code (default: "en")
            output_file_name: Base filename for output
            rvc_voice: RVC voice model or "Disabled"
            rvc_pitch: RVC pitch adjustment (-24 to 24)
            **kwargs: Additional parameters for the API
            
        Returns:
            API response as dict
        """
        data = {
            "text_input": text,
            "text_filtering": "standard",
            "character_voice_gen": character_voice,
            "narrator_enabled": "false",
            "narrator_voice_gen": character_voice,
            "text_not_inside": "character",
            "language": language,
            "output_file_name": output_file_name,
            "output_file_timestamp": "true",
            "autoplay": "false",
            "autoplay_volume": "0.8",
            "rvccharacter_voice_gen": rvc_voice,
            "rvccharacter_pitch": str(rvc_pitch),
            "rvcnarrator_voice_gen": "Disabled",
            "rvcnarrator_pitch": "0",
        }
        
        # Add any additional parameters
        data.update(kwargs)
        
        response = requests.post(self.api_endpoint, data=data, timeout=120)
        response.raise_for_status()
        
        return response.json()
    
    def generate_long_text(
        self,
        text: str,
        character_voice: str,
        chunk_size: int = 2,
        language: str = "en",
        output_file_name: str = "output",
        rvc_voice: str = "Disabled",
        rvc_pitch: float = 0,
        progress_callback: Optional[callable] = None,
        **kwargs
    ) -> List[dict]:
        """
        Generate TTS for long text with automatic chunking.
        
        Args:
            text: Long text to generate (any length)
            character_voice: Voice to use
            chunk_size: Number of sentences per chunk (default: 2)
            language: Language code (default: "en")
            output_file_name: Base filename for output
            rvc_voice: RVC voice model or "Disabled"
            rvc_pitch: RVC pitch adjustment
            progress_callback: Optional callback function(current, total, chunk_text)
            **kwargs: Additional API parameters
            
        Returns:
            List of API responses for each chunk
        """
        # Clean and split text
        cleaned_text = self.clean_text(text)
        sentences = self.split_into_sentences(cleaned_text)
        chunks = self.create_chunks(sentences, chunk_size)
        
        print(f"Text split into {len(chunks)} chunks")
        print(f"Total word count: {len(cleaned_text.split())}")
        
        results = []
        
        # Process each chunk
        for i, chunk in enumerate(chunks, 1):
            print(f"\nGenerating chunk {i}/{len(chunks)}")
            print(f"Text preview: {chunk[:100]}...")
            
            if progress_callback:
                progress_callback(i, len(chunks), chunk)
            
            try:
                result = self.generate_chunk(
                    text=chunk,
                    character_voice=character_voice,
                    language=language,
                    output_file_name=f"{output_file_name}_{i:05d}",
                    rvc_voice=rvc_voice,
                    rvc_pitch=rvc_pitch,
                    **kwargs
                )
                
                results.append(result)
                print(f"✓ Generated: {result.get('output_file_url', 'N/A')}")
                
            except Exception as e:
                print(f"✗ Error generating chunk {i}: {e}")
                results.append({"error": str(e), "chunk": i})
        
        print(f"\n✓ Complete! Generated {len(results)} chunks")
        return results


def example_usage():
    """Example usage of the chunked TTS generator."""
    
    # Initialize
    tts = AllTalkChunkedTTS(api_base="http://127.0.0.1:7851")
    
    # Long text example
    long_text = """
    This is a very long text that needs to be split into multiple chunks.
    The AllTalk TTS generator can handle texts of any length by automatically
    splitting them into manageable pieces. Each piece is generated separately
    and can be played back or saved. This is useful for generating audiobooks,
    long narrations, or any content that exceeds the standard character limits.
    
    You can customize the chunk size to control how many sentences are processed
    together. Smaller chunks mean more API calls but faster individual generation.
    Larger chunks mean fewer calls but each one takes longer to generate.
    
    The system automatically cleans the text, removing unwanted characters and
    normalizing punctuation. It then splits by sentence boundaries and groups
    them according to your specified chunk size.
    """
    
    # Generate with chunking
    results = tts.generate_long_text(
        text=long_text,
        character_voice="female_06.wav",  # Change to your preferred voice
        chunk_size=2,  # Process 2 sentences at a time
        language="en",
        output_file_name="my_long_audio"
    )
    
    # Print results
    print("\n" + "="*50)
    print("Generation Results:")
    print("="*50)
    for i, result in enumerate(results, 1):
        if "error" in result:
            print(f"Chunk {i}: ERROR - {result['error']}")
        else:
            print(f"Chunk {i}: {result.get('output_file_url', 'N/A')}")


if __name__ == "__main__":
    example_usage()
