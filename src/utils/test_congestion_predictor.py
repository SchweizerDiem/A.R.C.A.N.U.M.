"""
Testes unitários para o CongestionPredictor

Execução:
    pytest src/utils/test_congestion_predictor.py -v
"""

import pytest
import numpy as np
from CongestionPredictor import CongestionPredictor


class TestCongestionPredictor:
    """Testes para a classe CongestionPredictor"""
    
    def test_initialization(self):
        """Testa a inicialização do preditor"""
        predictor = CongestionPredictor(congestion_threshold=5.0, min_samples_to_train=10)
        
        assert predictor.congestion_threshold == 5.0
        assert predictor.min_samples_to_train == 10
        assert predictor.is_trained == False
        assert predictor.total_samples_collected == 0
        assert len(predictor.training_features) == 0
    
    def test_add_sample(self):
        """Testa a adição de amostras"""
        predictor = CongestionPredictor(min_samples_to_train=5)
        
        features = [10.0, 8.5, 2.3, 15.0]
        label = 0
        
        predictor.add_sample(features, label)
        
        assert len(predictor.training_features) == 1
        assert len(predictor.training_labels) == 1
        assert predictor.total_samples_collected == 1
    
    def test_should_train(self):
        """Testa a lógica de quando treinar"""
        predictor = CongestionPredictor(min_samples_to_train=3)
        
        assert predictor.should_train() == False
        
        # Adicionar amostras
        for i in range(3):
            predictor.add_sample([10.0, 8.0, 1.0, 10.0], 0)
        
        assert predictor.should_train() == True
    
    def test_training_with_synthetic_data(self):
        """Testa o treinamento com dados sintéticos"""
        predictor = CongestionPredictor(min_samples_to_train=10)
        
        # Criar dados sintéticos
        # Classe 0: Tráfego normal (alta velocidade, poucos veículos)
        for i in range(10):
            features = [5.0 + i, 15.0 + i, 2.0, 8.0]
            predictor.add_sample(features, 0)
        
        # Classe 1: Congestionamento (baixa velocidade, muitos veículos)
        for i in range(10):
            features = [50.0 + i, 3.0, 5.0, 80.0]
            predictor.add_sample(features, 1)
        
        # Treinar
        success = predictor.train()
        
        assert success == True
        assert predictor.is_trained == True
        assert predictor.total_trainings == 1
    
    def test_prediction_before_training(self):
        """Testa previsão antes do treinamento (deve usar heurística)"""
        predictor = CongestionPredictor(congestion_threshold=5.0)
        
        # Tráfego normal (velocidade alta)
        features_normal = [10.0, 15.0, 2.0, 10.0]
        prediction = predictor.predict(features_normal)
        assert prediction == 0
        
        # Congestionamento (velocidade baixa)
        features_congested = [50.0, 2.0, 5.0, 80.0]
        prediction = predictor.predict(features_congested)
        assert prediction == 1
    
    def test_prediction_after_training(self):
        """Testa previsão após treinamento"""
        predictor = CongestionPredictor(min_samples_to_train=10)
        
        # Criar e treinar com dados sintéticos
        for i in range(10):
            predictor.add_sample([5.0 + i, 15.0, 2.0, 8.0], 0)
        for i in range(10):
            predictor.add_sample([50.0 + i, 3.0, 5.0, 80.0], 1)
        
        predictor.train()
        
        # Testar previsão
        features_normal = [10.0, 15.0, 2.0, 10.0]
        prediction = predictor.predict(features_normal)
        assert prediction == 0
        
        features_congested = [55.0, 3.0, 5.0, 85.0]
        prediction = predictor.predict(features_congested)
        assert prediction == 1
    
    def test_congestion_probability(self):
        """Testa o cálculo de probabilidade"""
        predictor = CongestionPredictor(congestion_threshold=5.0)
        
        # Tráfego normal
        features_normal = [10.0, 15.0, 2.0, 10.0]
        prob = predictor.get_congestion_probability(features_normal)
        assert 0.0 <= prob <= 1.0
        assert prob < 0.5  # Deve ser baixa probabilidade
        
        # Congestionamento
        features_congested = [50.0, 2.0, 5.0, 80.0]
        prob = predictor.get_congestion_probability(features_congested)
        assert 0.0 <= prob <= 1.0
        assert prob > 0.5  # Deve ser alta probabilidade
    
    def test_get_stats(self):
        """Testa a obtenção de estatísticas"""
        predictor = CongestionPredictor(min_samples_to_train=5)
        
        predictor.add_sample([10.0, 8.0, 1.0, 10.0], 0)
        predictor.add_sample([15.0, 7.0, 2.0, 12.0], 0)
        
        stats = predictor.get_stats()
        
        assert stats['is_trained'] == False
        assert stats['total_samples_collected'] == 2
        assert stats['total_trainings'] == 0
        assert stats['samples_in_buffer'] == 2
        assert stats['min_samples_to_train'] == 5
    
    def test_training_with_single_class(self):
        """Testa que o treinamento falha graciosamente com apenas uma classe"""
        predictor = CongestionPredictor(min_samples_to_train=5)
        
        # Adicionar apenas amostras da classe 0
        for i in range(10):
            predictor.add_sample([10.0, 15.0, 2.0, 10.0], 0)
        
        # Treinar deve retornar False (não há variabilidade)
        success = predictor.train()
        assert success == False
        assert predictor.is_trained == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
