import os
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from preprocesamiento import limpiar_texto

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "dataset", "corpus_agro_ica.csv")
MODEL_DIR = os.path.join(BASE_DIR, "..", "modelos")
os.makedirs(MODEL_DIR, exist_ok=True)

def entrenar_modelos():
    df = pd.read_csv(DATA_PATH)
    df["texto_limpio"] = df["texto"].apply(limpiar_texto)

    # 1. Evaluación y entrenamiento del clasificador de intenciones
    X_train, X_test, y_train, y_test = train_test_split(
        df["texto_limpio"], df["intencion"], test_size=0.2, random_state=42, stratify=df["intencion"]
    )

    pipe_intencion = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(C=4.0, max_iter=1000))
    ])
    pipe_intencion.fit(X_train, y_train)

    print("=== REPORTE DE CLASIFICACIÓN DE INTENCIONES (TEST 20%) ===")
    print(classification_report(y_test, pipe_intencion.predict(X_test)))

    # Reentrenar con el 100% del dataset para producción
    pipe_intencion.fit(df["texto_limpio"], df["intencion"])
    joblib.dump(pipe_intencion, os.path.join(MODEL_DIR, "modelo_intenciones.joblib"))

    # 2. Entrenamiento del clasificador de sentimiento
    pipe_sentimiento = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(C=3.0, max_iter=1000))
    ])
    pipe_sentimiento.fit(df["texto_limpio"], df["sentimiento"])
    joblib.dump(pipe_sentimiento, os.path.join(MODEL_DIR, "modelo_sentimiento.joblib"))

    print("Artefactos guardados exitosamente en:", MODEL_DIR)

if __name__ == "__main__":
    entrenar_modelos()
