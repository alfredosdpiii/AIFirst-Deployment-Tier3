import os
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Product:
    """Product information structure"""
    title: str
    url: str
    snippet: str
    summary: Optional[str] = None
    price: Optional[float] = None
    specs: Optional[Dict] = None


class ScoutAgent:
    """Agent responsible for searching and gathering product information"""
    
    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")
        self.base_url = "https://api.tavily.com"
    
    def search(self, query: str, max_results: int = 8) -> List[Dict]:
        """
        Search for products using Tavily API
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of search results with title, url, and snippet
        """
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/search",
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                
            data = response.json()
            results = []
            
            for result in data.get("results", []):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "snippet": result.get("content", "")[:500]
                })
            
            return results
            
        except Exception as e:
            print(f"Error searching with Tavily: {e}")
            return []


class JudgeAgent:
    """Agent responsible for analyzing and ranking products"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    def extract_product_info(self, snippet: str) -> str:
        """
        Extract key specs, price, pros & cons from product snippet
        
        Args:
            snippet: Product snippet text
            
        Returns:
            Structured summary of product information
        """
        system_prompt = """You are a meticulous shopping researcher. Extract and summarize:
        1. Key specifications
        2. Price (in USD if available)
        3. Main pros and cons
        4. Any notable features
        
        Format as a concise summary."""
        
        return self._call_openai(system_prompt, snippet)
    
    def judge_products(self, question: str, products: List[Dict]) -> Dict:
        """
        Analyze products and provide recommendation
        
        Args:
            question: User's shopping question
            products: List of enriched product information
            
        Returns:
            Verdict with winner, ranking, and reasons
        """
        system_prompt = """You are an expert tech reviewer.
        Analyze the products and return a JSON response with:
        - winner: string (best overall product or chosen between A/B)
        - ranking: list (ordered product names from best to worst)
        - reasons: list of strings (key reasons for the recommendation)
        
        Consider factors like value, specs, reliability, and user needs."""
        
        user_prompt = f"Question: {question}\n\nProduct briefs:\n{json.dumps(products, indent=2)}"
        
        response = self._call_openai(system_prompt, user_prompt, json_mode=True)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback structure if JSON parsing fails
            return {
                "winner": "Unable to determine",
                "ranking": [],
                "reasons": ["Error parsing recommendation"]
            }
    
    def _call_openai(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """Call OpenAI API"""
        import openai
        
        client = openai.OpenAI(api_key=self.api_key)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3 if json_mode else 0.2,
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            return ""
    


class ShopSage:
    """Main shopping recommendation system"""
    
    def __init__(self):
        self.scout = ScoutAgent()
        self.judge = JudgeAgent()
    
    def run_pipeline(self, question: str) -> Dict:
        """
        Run the complete recommendation pipeline
        
        Args:
            question: User's shopping question
            
        Returns:
            Complete recommendation with verdict, ranking, reasons, and sources
        """
        # Detect if this is an A vs B comparison
        vs_pattern = r"(.+?)\s+vs\.?\s+(.+?)(?:\?|$)"
        vs_match = re.search(vs_pattern, question, re.IGNORECASE)
        
        if vs_match:
            # Handle A vs B comparison
            product_a = vs_match.group(1).strip()
            product_b = vs_match.group(2).strip()
            
            # Search for both products
            hits_a = self.scout.search(product_a, max_results=4)
            hits_b = self.scout.search(product_b, max_results=4)
            hits = hits_a + hits_b
        else:
            # Regular search
            hits = self.scout.search(question)
        
        # Enrich product information
        enriched_products = []
        for hit in hits:
            summary = self.judge.extract_product_info(hit["snippet"])
            enriched_products.append({
                "title": hit["title"],
                "url": hit["url"],
                "snippet": hit["snippet"],
                "summary": summary
            })
        
        # Get recommendation
        verdict = self.judge.judge_products(question, enriched_products)
        
        # Return complete result
        return {
            "query": question,
            "winner": verdict.get("winner", ""),
            "ranking": verdict.get("ranking", []),
            "reasons": verdict.get("reasons", []),
            "sources": enriched_products[:4]  # Keep top 4 for citation
        }


# Convenience functions for backward compatibility
def scout(query: str, k: int = 8) -> List[Dict]:
    """Backward compatible scout function"""
    agent = ScoutAgent()
    return agent.search(query, k)


def enrich(hits: List[Dict]) -> List[Dict]:
    """Backward compatible enrich function"""
    judge = JudgeAgent()
    for hit in hits:
        hit["summary"] = judge.extract_product_info(hit["snippet"])
    return hits


def judge(question: str, products: List[Dict]) -> Dict:
    """Backward compatible judge function"""
    agent = JudgeAgent()
    return agent.judge_products(question, products)


def run_pipeline(question: str) -> Dict:
    """Backward compatible pipeline function"""
    sage = ShopSage()
    return sage.run_pipeline(question)