"""
Memory-efficient PDF processing module for PaintScope
Handles PDF to image conversion with caching and memory management
"""

import fitz  # PyMuPDF
import base64
import io
from PIL import Image
from typing import List, Dict, Optional, Tuple
import gc
import hashlib
import tempfile
import os
import streamlit as st

class PDFProcessor:
    """Memory-efficient PDF processor with caching and cleanup"""
    
    # Configuration
    DEFAULT_DPI = 150  # Standard resolution for analysis
    MAX_IMAGE_DIMENSION = 2000  # Max width or height in pixels
    JPEG_QUALITY = 90  # JPEG compression quality
    MAX_PAGES_IN_MEMORY = 15  # Maximum pages to keep in memory at once
    MAX_BATCH_SIZE = 5  # Maximum pages to process in one batch
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp(prefix="paintscope_")
        self.current_pdf_hash = None
        self.page_cache = {}
        
    def __del__(self):
        """Cleanup temporary files on deletion"""
        self.cleanup()
    
    def cleanup(self):
        """Clean up all temporary files and cache"""
        # Clear page cache
        self.page_cache.clear()
        
        # Remove temp directory
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        
        # Force garbage collection
        gc.collect()
    
    def get_pdf_hash(self, pdf_bytes: bytes) -> str:
        """Generate hash for PDF content"""
        return hashlib.md5(pdf_bytes).hexdigest()
    
    def process_pdf_info(self, pdf_bytes: bytes) -> Dict:
        """Get PDF information without processing all pages"""
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        info = {
            'page_count': len(pdf_document),
            'pdf_hash': self.get_pdf_hash(pdf_bytes),
            'metadata': pdf_document.metadata
        }
        pdf_document.close()
        return info
    
    def convert_page_to_image(self, pdf_bytes: bytes, page_num: int, 
                            quality: str = 'medium') -> Optional[str]:
        """
        Convert a single PDF page to base64 image
        
        Args:
            pdf_bytes: PDF file bytes
            page_num: Page number (0-indexed)
            quality: 'low', 'medium', or 'high'
        
        Returns:
            Base64 encoded image string
        """
        pdf_hash = self.get_pdf_hash(pdf_bytes)
        cache_key = f"{pdf_hash}_{page_num}_{quality}"
        
        # Check cache
        if cache_key in self.page_cache:
            return self.page_cache[cache_key]
        
        # Quality settings
        quality_settings = {
            'low': {'dpi': 72, 'jpeg_quality': 70},
            'medium': {'dpi': 150, 'jpeg_quality': 85},
            'high': {'dpi': 200, 'jpeg_quality': 95}
        }
        
        settings = quality_settings.get(quality, quality_settings['medium'])
        
        try:
            # Open PDF
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            
            if page_num >= len(pdf_document):
                pdf_document.close()
                return None
            
            # Get page
            page = pdf_document[page_num]
            
            # Calculate matrix for desired DPI
            zoom = settings['dpi'] / 72.0
            mat = fitz.Matrix(zoom, zoom)
            
            # Render page
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image for compression
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # Resize if too large
            if img.width > self.MAX_IMAGE_DIMENSION or img.height > self.MAX_IMAGE_DIMENSION:
                img.thumbnail((self.MAX_IMAGE_DIMENSION, self.MAX_IMAGE_DIMENSION), 
                             Image.Resampling.LANCZOS)
            
            # Convert to RGB if necessary (for JPEG)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = background
            
            # Save as JPEG with compression
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG", quality=settings['jpeg_quality'], optimize=True)
            img_base64 = base64.b64encode(buffered.getvalue()).decode()
            
            # Clean up
            pdf_document.close()
            del img
            del pix
            
            # Cache if space allows
            if len(self.page_cache) < self.MAX_PAGES_IN_MEMORY:
                self.page_cache[cache_key] = img_base64
            else:
                # Clear oldest cache entry
                if self.page_cache:
                    self.page_cache.pop(next(iter(self.page_cache)))
                self.page_cache[cache_key] = img_base64
            
            return img_base64
            
        except Exception as e:
            print(f"Error converting page {page_num}: {str(e)}")
            return None
    
    def convert_pages_batch(self, pdf_bytes: bytes, page_numbers: List[int], 
                           quality: str = 'medium') -> Dict[int, str]:
        """
        Convert multiple PDF pages to images
        
        Args:
            pdf_bytes: PDF file bytes
            page_numbers: List of page numbers to convert (0-indexed)
            quality: Image quality setting
        
        Returns:
            Dictionary mapping page number to base64 image
        """
        results = {}
        # Process in limited batch sizes to avoid spikes
        for i in range(0, len(page_numbers), self.MAX_BATCH_SIZE):
            batch = page_numbers[i:i + self.MAX_BATCH_SIZE]
            for page_num in batch:
                img_base64 = self.convert_page_to_image(pdf_bytes, page_num, quality)
                if img_base64:
                    results[page_num] = img_base64
        return results
    
    def get_page_preview(self, pdf_bytes: bytes, page_num: int) -> Optional[str]:
        """Get low-quality preview of a page"""
        return self.convert_page_to_image(pdf_bytes, page_num, quality='low')
    
    def get_page_for_analysis(self, pdf_bytes: bytes, page_num: int) -> Optional[str]:
        """Get medium-quality image suitable for AI analysis"""
        return self.convert_page_to_image(pdf_bytes, page_num, quality='medium')
    
    def extract_text_from_page(self, pdf_bytes: bytes, page_num: int) -> str:
        """Extract text content from a PDF page"""
        try:
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
            if page_num >= len(pdf_document):
                pdf_document.close()
                return ""
            
            page = pdf_document[page_num]
            text = page.get_text()
            pdf_document.close()
            return text
        except:
            return ""
    
    def clear_cache(self):
        """Clear the page cache to free memory"""
        self.page_cache.clear()
        gc.collect()


class StreamlitPDFManager:
    """Manages PDF processing for Streamlit with session state integration"""
    
    def __init__(self):
        # Initialize processor in session state if not exists
        if 'pdf_processor' not in st.session_state:
            st.session_state.pdf_processor = PDFProcessor()
        self.processor = st.session_state.pdf_processor
    
    def process_pdf_upload(self, pdf_bytes: bytes, max_initial_pages: int = 10) -> Dict:
        """
        Process uploaded PDF with memory-efficient approach
        
        Args:
            pdf_bytes: PDF file bytes
            max_initial_pages: Maximum pages to process initially
        
        Returns:
            Dictionary with PDF info and initial pages
        """
        # Clear previous PDF data
        self.cleanup_previous()
        
        # Get PDF info
        info = self.processor.process_pdf_info(pdf_bytes)
        
        # Process initial pages for analysis
        initial_pages = min(max_initial_pages, info['page_count'])
        page_images = {}
        
        for i in range(initial_pages):
            img = self.processor.get_page_for_analysis(pdf_bytes, i)
            if img:
                page_images[i] = img
        
        return {
            'info': info,
            'initial_pages': page_images,
            'total_pages': info['page_count']
        }
    
    def get_pages_on_demand(self, pdf_bytes: bytes, page_numbers: List[int]) -> Dict[int, str]:
        """Load specific pages on demand"""
        return self.processor.convert_pages_batch(pdf_bytes, page_numbers, quality='medium')
    
    def cleanup_previous(self):
        """Clean up previous PDF data from session state"""
        # Clear old PDF images from session state
        if 'pdf_images' in st.session_state:
            del st.session_state.pdf_images
        
        # Clear processor cache
        self.processor.clear_cache()
        
        # Force garbage collection
        gc.collect()
    
    def get_memory_usage(self) -> Dict:
        """Get current memory usage stats"""
        import psutil
        import sys
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size in MB
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size in MB
            'cache_size': len(self.processor.page_cache),
            'session_state_size': sys.getsizeof(st.session_state) / 1024 / 1024  # Approximate
        }