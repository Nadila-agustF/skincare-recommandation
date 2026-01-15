import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class SkincareRecommender:
    def __init__(self, df):
        self.df = df
        self.tfidf = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = self.tfidf.fit_transform(df["combined_text"])
        self.cosine_sim = cosine_similarity(self.tfidf_matrix)
    
    def recommend(self, skin_types, categories, top_n=5):
        """Memberikan rekomendasi produk"""
        filtered_idx = []
        
        for idx, row in self.df.iterrows():
            if skin_types and not any(s in row["skin_type"] for s in skin_types):
                continue
            if categories and not any(c in row["category"] for c in categories):
                continue
            filtered_idx.append(idx)
        
        if not filtered_idx:
            return pd.DataFrame()
        
        # Hitung similarity
        sim_scores = self.cosine_sim[filtered_idx].mean(axis=0)
        
        scores_df = pd.DataFrame({
            "index": range(len(sim_scores)),
            "similarity": sim_scores
        })
        
        scores_df = scores_df[scores_df["index"].isin(filtered_idx)]
        scores_df = scores_df.sort_values(by="similarity", ascending=False)
        
        top_indices = scores_df.head(top_n)["index"].tolist()
        return self.df.loc[top_indices]