"""
Clarification logic for similar-looking diseases
"""
from typing import Dict, List, Optional
from content.disease.clarifications import DISEASE_CLARIFICATIONS

class ClarificationLogic:
    """Handle disease clarification questions and answers"""
    
    @staticmethod
    def needs_clarification(disease: str, confidence: float) -> bool:
        """
        Check if disease needs clarification
        Args:
            disease: Disease name
            confidence: Confidence score
        Returns:
            bool: True if clarification needed
        """
        if confidence >= 70:  # High confidence, no clarification needed
            return False
        
        return disease in DISEASE_CLARIFICATIONS
    
    @staticmethod
    def get_clarification_question(disease: str) -> Optional[str]:
        """
        Get clarification question for disease
        Args:
            disease: Disease name
        Returns:
            Question string or None
        """
        clarification = DISEASE_CLARIFICATIONS.get(disease)
        if clarification and clarification.get('questions'):
            return clarification['questions'][0]['question']
        return None
    
    @staticmethod
    def process_answer(disease: str, answer: str) -> Dict:
        """
        Process user's answer to clarification question
        Args:
            disease: Disease name
            answer: User's answer (yes/no)
        Returns:
            Dict with refined diagnosis
        """
        clarification = DISEASE_CLARIFICATIONS.get(disease, {})
        
        result = {
            "original_disease": disease,
            "refined_disease": disease,
            "confidence_boost": 0,
            "message": ""
        }
        
        if not clarification or not clarification.get('questions'):
            return result
        
        question_data = clarification['questions'][0]
        
        if answer.lower() == 'yes':
            result['message'] = question_data.get('yes', '')
            result['confidence_boost'] = 15
        else:
            result['message'] = question_data.get('no', '')
            result['confidence_boost'] = 5
        
        return result
    
    @staticmethod
    def get_similar_diseases(disease: str) -> List[str]:
        """Get list of diseases similar to current one"""
        clarification = DISEASE_CLARIFICATIONS.get(disease)
        if clarification:
            return clarification.get('similar_to', [])
        return []
    
    @staticmethod
    def get_disease_complexes() -> Dict:
        """Get information about disease complexes"""
        complexes = {}
        
        for key, value in DISEASE_CLARIFICATIONS.items():
            if 'complex' in key.lower() or value.get('name', '').lower().find('complex') >= 0:
                complexes[key] = value
        
        return complexes