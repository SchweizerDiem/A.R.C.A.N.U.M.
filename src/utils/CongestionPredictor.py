"""
CongestionPredictor - Modelo de Machine Learning para previsão de congestionamento

Este módulo implementa um modelo de Regressão Logística para prever a probabilidade
de congestionamento baseado em métricas de tráfego em tempo real.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import traci
from typing import List, Tuple, Optional
import warnings
import json
import pickle
import os

warnings.filterwarnings('ignore')


class CongestionPredictor:
    """
    Preditor de congestionamento usando Regressão Logística.
    
    Features utilizadas:
    - num_vehicles: Número de veículos na simulação
    - avg_speed: Velocidade média dos veículos (m/s)
    - speed_variance: Variância da velocidade
    - vehicle_density: Densidade de veículos por km
    
    Target:
    - is_congested: 1 se congestionado, 0 caso contrário
    """
    
    def __init__(self, congestion_threshold: float = 5.0, min_samples_to_train: int = 50, 
                 data_dir: str = "ml_data"):
        """
        Inicializa o preditor.
        
        Args:
            congestion_threshold: Velocidade média abaixo da qual considera-se congestionamento (m/s)
            min_samples_to_train: Número mínimo de amostras antes de treinar o modelo
            data_dir: Diretório para salvar/carregar dados persistentes
        """
        self.model = LogisticRegression(random_state=42, max_iter=1000)
        self.scaler = StandardScaler()
        self.congestion_threshold = congestion_threshold
        self.min_samples_to_train = min_samples_to_train
        self.data_dir = data_dir
        
        # Criar diretório de dados se não existir
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Armazenamento de dados para treinamento
        self.training_features: List[List[float]] = []
        self.training_labels: List[int] = []
        
        # Estado do modelo
        self.is_trained = False
        self.total_samples_collected = 0
        self.total_trainings = 0
        
        # Cache para cálculo de densidade
        self.total_network_length: Optional[float] = None
        
        # Tentar carregar dados persistentes
        self.load_data()
    
    def _get_network_length(self) -> float:
        """
        Calcula o comprimento total da rede (em metros).
        Cacheia o resultado para evitar recalcular.
        """
        if self.total_network_length is None:
            try:
                edge_ids = traci.edge.getIDList()
                self.total_network_length = sum(
                    traci.edge.getLength(edge_id) for edge_id in edge_ids
                )
            except Exception as e:
                print(f"[Predictor] Erro ao calcular comprimento da rede: {e}")
                self.total_network_length = 10000.0  # Valor padrão de 10km
        
        return self.total_network_length
    
    def collect_features(self) -> Optional[Tuple[List[float], int]]:
        """
        Coleta features da simulação SUMO atual.
        
        Returns:
            Tupla (features, label) ou None se não houver dados suficientes
            - features: [num_vehicles, avg_speed, speed_variance, vehicle_density]
            - label: 1 se congestionado, 0 caso contrário
        """
        if not traci.isLoaded():
            return None
        
        try:
            vehicle_ids = traci.vehicle.getIDList()
            num_vehicles = len(vehicle_ids)
            
            # Precisa de pelo menos 1 veículo para calcular features
            if num_vehicles == 0:
                return None
            
            # Coletar velocidades
            speeds = [traci.vehicle.getSpeed(veh_id) for veh_id in vehicle_ids]
            avg_speed = np.mean(speeds)
            speed_variance = np.var(speeds)
            
            # Calcular densidade (veículos por km)
            network_length_km = self._get_network_length() / 1000.0
            vehicle_density = num_vehicles / network_length_km if network_length_km > 0 else 0
            
            # Determinar label (congestionado ou não)
            # Critério: velocidade média < threshold OU densidade muito alta
            is_congested = 1 if (avg_speed < self.congestion_threshold or vehicle_density > 50) else 0
            
            features = [
                float(num_vehicles),
                float(avg_speed),
                float(speed_variance),
                float(vehicle_density)
            ]
            
            return (features, is_congested)
            
        except Exception as e:
            print(f"[Predictor] Erro ao coletar features: {e}")
            return None
    
    def add_sample(self, features: List[float], label: int) -> None:
        """
        Adiciona uma amostra ao dataset de treinamento.
        
        Args:
            features: Lista de features
            label: Label (0 ou 1)
        """
        self.training_features.append(features)
        self.training_labels.append(label)
        self.total_samples_collected += 1
    
    def should_train(self) -> bool:
        """
        Verifica se deve treinar o modelo.
        
        Returns:
            True se houver amostras suficientes para treinar
        """
        return len(self.training_features) >= self.min_samples_to_train
    
    def train(self) -> bool:
        """
        Treina o modelo com as amostras coletadas.
        
        Returns:
            True se o treinamento foi bem-sucedido
        """
        if not self.should_train():
            return False
        
        try:
            X = np.array(self.training_features)
            y = np.array(self.training_labels)
            
            # Verificar se há pelo menos 2 classes
            unique_labels = np.unique(y)
            if len(unique_labels) < 2:
                print(f"[Predictor] Aviso: Apenas uma classe presente nos dados ({unique_labels}). Aguardando mais variabilidade.")
                return False
            
            # Normalizar features
            X_scaled = self.scaler.fit_transform(X)
            
            # Treinar modelo
            self.model.fit(X_scaled, y)
            self.is_trained = True
            self.total_trainings += 1
            
            # Manter todos os dados coletados (sem limitação)
            # Nota: Em execuções muito longas, considere adicionar um limite maior se necessário
            
            print(f"[Predictor] ✓ Modelo treinado com {len(X)} amostras (Treinamento #{self.total_trainings})")
            
            # Salvar dados automaticamente após treinar
            self.save_data()
            
            return True
            
        except Exception as e:
            print(f"[Predictor] Erro ao treinar modelo: {e}")
            return False
    
    def predict(self, features: List[float]) -> int:
        """
        Faz previsão de congestionamento.
        
        Args:
            features: Lista de features
            
        Returns:
            0 (não congestionado) ou 1 (congestionado)
        """
        if not self.is_trained:
            # Se não treinado, usa heurística simples
            avg_speed = features[1]
            return 1 if avg_speed < self.congestion_threshold else 0
        
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            prediction = self.model.predict(X_scaled)[0]
            return int(prediction)
        except Exception as e:
            print(f"[Predictor] Erro ao fazer previsão: {e}")
            # Fallback para heurística
            avg_speed = features[1]
            return 1 if avg_speed < self.congestion_threshold else 0
    
    def get_congestion_probability(self, features: List[float]) -> float:
        """
        Retorna a probabilidade de congestionamento.
        
        Args:
            features: Lista de features
            
        Returns:
            Probabilidade entre 0.0 e 1.0
        """
        if not self.is_trained:
            # Se não treinado, usa heurística simples
            avg_speed = features[1]
            # Probabilidade inversamente proporcional à velocidade
            prob = max(0.0, min(1.0, (self.congestion_threshold - avg_speed) / self.congestion_threshold))
            return prob
        
        try:
            X = np.array([features])
            X_scaled = self.scaler.transform(X)
            # Probabilidade da classe 1 (congestionado)
            probability = self.model.predict_proba(X_scaled)[0][1]
            return float(probability)
        except Exception as e:
            print(f"[Predictor] Erro ao calcular probabilidade: {e}")
            # Fallback para heurística
            avg_speed = features[1]
            prob = max(0.0, min(1.0, (self.congestion_threshold - avg_speed) / self.congestion_threshold))
            return prob
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do preditor.
        
        Returns:
            Dicionário com estatísticas
        """
        return {
            'is_trained': self.is_trained,
            'total_samples_collected': self.total_samples_collected,
            'total_trainings': self.total_trainings,
            'samples_in_buffer': len(self.training_features),
            'min_samples_to_train': self.min_samples_to_train
        }
    
    def save_data(self) -> bool:
        """
        Salva dados de treinamento e modelo em arquivos.
        
        Salva:
        - training_data.json: Features, labels e estatísticas
        - model.pkl: Modelo treinado e scaler (se treinado)
        
        Returns:
            True se salvou com sucesso
        """
        try:
            # Salvar dados de treinamento em JSON
            data_path = os.path.join(self.data_dir, 'training_data.json')
            training_data = {
                'features': self.training_features,
                'labels': self.training_labels,
                'stats': {
                    'total_samples_collected': self.total_samples_collected,
                    'total_trainings': self.total_trainings,
                    'is_trained': self.is_trained,
                    'congestion_threshold': self.congestion_threshold,
                    'min_samples_to_train': self.min_samples_to_train
                }
            }
            
            with open(data_path, 'w') as f:
                json.dump(training_data, f, indent=2)
            
            # Salvar modelo treinado em pickle (se treinado)
            if self.is_trained:
                model_path = os.path.join(self.data_dir, 'model.pkl')
                model_data = {
                    'model': self.model,
                    'scaler': self.scaler
                }
                with open(model_path, 'wb') as f:
                    pickle.dump(model_data, f)
            
            print(f"[Predictor] 💾 Dados salvos em {self.data_dir}/")
            return True
            
        except Exception as e:
            print(f"[Predictor] Erro ao salvar dados: {e}")
            return False
    
    def load_data(self) -> bool:
        """
        Carrega dados de treinamento e modelo de arquivos.
        
        Returns:
            True se carregou com sucesso
        """
        try:
            # Carregar dados de treinamento
            data_path = os.path.join(self.data_dir, 'training_data.json')
            if os.path.exists(data_path):
                with open(data_path, 'r') as f:
                    training_data = json.load(f)
                
                self.training_features = training_data['features']
                self.training_labels = training_data['labels']
                self.total_samples_collected = training_data['stats']['total_samples_collected']
                self.total_trainings = training_data['stats']['total_trainings']
                
                print(f"[Predictor] 📂 Carregados {len(self.training_features)} amostras de treinamento")
            
            # Carregar modelo treinado
            model_path = os.path.join(self.data_dir, 'model.pkl')
            if os.path.exists(model_path):
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.model = model_data['model']
                self.scaler = model_data['scaler']
                self.is_trained = True
                
                print(f"[Predictor] 📂 Modelo treinado carregado (Treinamentos anteriores: {self.total_trainings})")
                return True
            
            return False
            
        except Exception as e:
            print(f"[Predictor] Aviso ao carregar dados: {e}")
            return False
    
    def clear_data(self) -> bool:
        """
        Limpa todos os dados persistentes (arquivos JSON e pickle).
        
        Returns:
            True se limpou com sucesso
        """
        try:
            data_path = os.path.join(self.data_dir, 'training_data.json')
            model_path = os.path.join(self.data_dir, 'model.pkl')
            
            if os.path.exists(data_path):
                os.remove(data_path)
            if os.path.exists(model_path):
                os.remove(model_path)
            
            print(f"[Predictor] 🗑️  Dados persistentes removidos")
            return True
            
        except Exception as e:
            print(f"[Predictor] Erro ao limpar dados: {e}")
            return False
