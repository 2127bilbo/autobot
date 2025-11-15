"""
Autobot Drop Predictor - Phase 3A
Predictive stock drop analysis using historical patterns

This module analyzes historical drop data to predict future drops:
- Day-of-week patterns (e.g., "Drops usually happen on Fridays")
- Time-of-day patterns (e.g., "Drops usually happen at 3 PM EST")
- Confidence scoring based on consistency
- Predictive alerts

Author: Bob (Bloomfield, IN)
Created: November 13, 2025
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
import statistics


class DropPredictor:
    """
    Analyzes historical drop patterns and predicts future drops.
    
    Features:
    - Historical drop analysis
    - Day/time pattern recognition
    - Confidence scoring
    - Next drop prediction
    """
    
    def __init__(self, db_path: str = "autobot.db"):
        self.db_path = db_path
        self._ensure_drop_history_table()
    
    def _ensure_drop_history_table(self):
        """Create drop_history table if it doesn't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS drop_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_url TEXT NOT NULL,
                    product_name TEXT,
                    site TEXT,
                    drop_time TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    price REAL,
                    stock_quantity INTEGER,
                    day_of_week INTEGER,
                    hour_of_day INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drop_history_url 
                ON drop_history(product_url)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drop_history_site 
                ON drop_history(site)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_drop_history_time 
                ON drop_history(drop_time)
            """)
            
            conn.commit()
            
        except Exception as e:
            print(f"[DropPredictor] Error creating drop_history table: {e}")
            conn.rollback()
        
        finally:
            conn.close()
    
    def record_drop(
        self,
        product_url: str,
        drop_time: datetime,
        product_name: str = None,
        site: str = None,
        price: float = None,
        stock_quantity: int = None
    ) -> int:
        """
        Record a drop in the history.
        
        Args:
            product_url: URL of the product
            drop_time: When the drop occurred
            product_name: Name of the product
            site: Site name
            price: Product price
            stock_quantity: Available stock quantity
            
        Returns:
            ID of the recorded drop
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            now = datetime.now().isoformat()
            drop_time_iso = drop_time.isoformat()
            day_of_week = drop_time.weekday()  # 0 = Monday, 6 = Sunday
            hour_of_day = drop_time.hour
            
            cursor.execute("""
                INSERT INTO drop_history 
                (product_url, product_name, site, drop_time, detected_at,
                 price, stock_quantity, day_of_week, hour_of_day)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (product_url, product_name, site, drop_time_iso, now,
                  price, stock_quantity, day_of_week, hour_of_day))
            
            drop_id = cursor.lastrowid
            conn.commit()
            
            print(f"[DropPredictor] Recorded drop #{drop_id} for {product_url}")
            return drop_id
            
        except Exception as e:
            conn.rollback()
            print(f"[DropPredictor] Error recording drop: {e}")
            raise
        
        finally:
            conn.close()
    
    def analyze_product(self, product_url: str) -> Dict:
        """
        Analyze historical drop patterns for a specific product.
        
        Args:
            product_url: URL of the product to analyze
            
        Returns:
            Dictionary with pattern analysis:
            {
                'total_drops': int,
                'date_range': (oldest, newest),
                'day_pattern': Counter,
                'hour_pattern': Counter,
                'most_common_day': str,
                'most_common_hour': int,
                'avg_days_between_drops': float,
                'confidence_score': float
            }
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get all historical drops for this product
            cursor.execute("""
                SELECT * FROM drop_history 
                WHERE product_url = ?
                ORDER BY drop_time ASC
            """, (product_url,))
            
            drops = [dict(row) for row in cursor.fetchall()]
            
            if not drops:
                return {
                    'total_drops': 0,
                    'confidence_score': 0.0,
                    'message': 'No historical data available'
                }
            
            # Analyze patterns
            day_counts = Counter()
            hour_counts = Counter()
            drop_dates = []
            
            for drop in drops:
                day_counts[drop['day_of_week']] += 1
                hour_counts[drop['hour_of_day']] += 1
                drop_dates.append(datetime.fromisoformat(drop['drop_time']))
            
            # Calculate date range
            oldest = drop_dates[0]
            newest = drop_dates[-1]
            
            # Calculate average days between drops
            if len(drop_dates) > 1:
                intervals = []
                for i in range(1, len(drop_dates)):
                    delta = (drop_dates[i] - drop_dates[i-1]).days
                    intervals.append(delta)
                avg_interval = statistics.mean(intervals)
            else:
                avg_interval = None
            
            # Find most common patterns
            most_common_day = day_counts.most_common(1)[0] if day_counts else None
            most_common_hour = hour_counts.most_common(1)[0] if hour_counts else None
            
            # Calculate confidence score
            confidence = self._calculate_confidence(
                total_drops=len(drops),
                day_consistency=most_common_day[1] / len(drops) if most_common_day else 0,
                hour_consistency=most_common_hour[1] / len(drops) if most_common_hour else 0,
                data_age_days=(datetime.now() - oldest).days
            )
            
            # Day names
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            return {
                'total_drops': len(drops),
                'date_range': (oldest.isoformat(), newest.isoformat()),
                'day_pattern': dict(day_counts),
                'hour_pattern': dict(hour_counts),
                'most_common_day': day_names[most_common_day[0]] if most_common_day else None,
                'most_common_day_count': most_common_day[1] if most_common_day else 0,
                'most_common_hour': most_common_hour[0] if most_common_hour else None,
                'most_common_hour_count': most_common_hour[1] if most_common_hour else 0,
                'avg_days_between_drops': avg_interval,
                'confidence_score': confidence
            }
            
        finally:
            conn.close()
    
    def analyze_site(self, site: str) -> Dict:
        """
        Analyze historical drop patterns for an entire site.
        
        Args:
            site: Site name to analyze
            
        Returns:
            Dictionary with site-wide pattern analysis
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Get all historical drops for this site
            cursor.execute("""
                SELECT * FROM drop_history 
                WHERE site = ?
                ORDER BY drop_time ASC
            """, (site,))
            
            drops = [dict(row) for row in cursor.fetchall()]
            
            if not drops:
                return {
                    'total_drops': 0,
                    'confidence_score': 0.0,
                    'message': 'No historical data available for this site'
                }
            
            # Analyze patterns
            day_counts = Counter()
            hour_counts = Counter()
            
            for drop in drops:
                day_counts[drop['day_of_week']] += 1
                hour_counts[drop['hour_of_day']] += 1
            
            # Find most common patterns
            most_common_day = day_counts.most_common(1)[0] if day_counts else None
            most_common_hour = hour_counts.most_common(1)[0] if hour_counts else None
            
            # Day names
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # Calculate confidence
            total = len(drops)
            confidence = self._calculate_confidence(
                total_drops=total,
                day_consistency=most_common_day[1] / total if most_common_day else 0,
                hour_consistency=most_common_hour[1] / total if most_common_hour else 0,
                data_age_days=30  # Assume recent data for site-wide
            )
            
            return {
                'site': site,
                'total_drops': total,
                'day_pattern': dict(day_counts),
                'hour_pattern': dict(hour_counts),
                'most_common_day': day_names[most_common_day[0]] if most_common_day else None,
                'most_common_day_percentage': (most_common_day[1] / total * 100) if most_common_day else 0,
                'most_common_hour': most_common_hour[0] if most_common_hour else None,
                'most_common_hour_percentage': (most_common_hour[1] / total * 100) if most_common_hour else 0,
                'confidence_score': confidence
            }
            
        finally:
            conn.close()
    
    def predict_next_drop(self, product_url: str) -> Dict:
        """
        Predict the next drop for a product based on historical patterns.
        
        Args:
            product_url: URL of the product
            
        Returns:
            Dictionary with prediction:
            {
                'predicted_time': datetime or None,
                'confidence': float,
                'pattern_description': str,
                'next_likely_day': str,
                'next_likely_hour': int,
                'rationale': str
            }
        """
        analysis = self.analyze_product(product_url)
        
        if analysis['total_drops'] == 0:
            return {
                'predicted_time': None,
                'confidence': 0.0,
                'pattern_description': 'No historical data',
                'rationale': 'Need at least 1 historical drop to make predictions'
            }
        
        if analysis['total_drops'] < 3:
            return {
                'predicted_time': None,
                'confidence': analysis['confidence_score'],
                'pattern_description': 'Insufficient data',
                'next_likely_day': analysis['most_common_day'],
                'next_likely_hour': analysis['most_common_hour'],
                'rationale': f'Only {analysis["total_drops"]} drops recorded. Need at least 3 for reliable predictions.'
            }
        
        # Build prediction
        now = datetime.now()
        
        # Find next occurrence of most common day
        most_common_day_num = list(analysis['day_pattern'].keys())[
            list(analysis['day_pattern'].values()).index(analysis['most_common_day_count'])
        ]
        
        # Calculate days until next occurrence
        current_day = now.weekday()
        days_ahead = (most_common_day_num - current_day) % 7
        if days_ahead == 0 and now.hour >= analysis['most_common_hour']:
            days_ahead = 7  # Next week if we've passed the hour today
        
        next_drop_date = now + timedelta(days=days_ahead)
        predicted_time = next_drop_date.replace(
            hour=analysis['most_common_hour'],
            minute=0,
            second=0,
            microsecond=0
        )
        
        # Build pattern description
        day_percentage = (analysis['most_common_day_count'] / analysis['total_drops']) * 100
        hour_percentage = (analysis['most_common_hour_count'] / analysis['total_drops']) * 100
        
        pattern_desc = (
            f"{analysis['most_common_day']}s at {analysis['most_common_hour']:02d}:00 "
            f"({day_percentage:.0f}% of drops)"
        )
        
        rationale = (
            f"Based on {analysis['total_drops']} historical drops, "
            f"{analysis['most_common_day_count']} occurred on {analysis['most_common_day']} "
            f"and {analysis['most_common_hour_count']} occurred at {analysis['most_common_hour']:02d}:00."
        )
        
        if analysis['avg_days_between_drops']:
            rationale += f" Average interval: {analysis['avg_days_between_drops']:.1f} days."
        
        return {
            'predicted_time': predicted_time.isoformat(),
            'confidence': analysis['confidence_score'],
            'pattern_description': pattern_desc,
            'next_likely_day': analysis['most_common_day'],
            'next_likely_hour': analysis['most_common_hour'],
            'rationale': rationale
        }
    
    def _calculate_confidence(
        self,
        total_drops: int,
        day_consistency: float,
        hour_consistency: float,
        data_age_days: int
    ) -> float:
        """
        Calculate confidence score for predictions.
        
        Args:
            total_drops: Number of historical drops
            day_consistency: Percentage of drops on most common day (0-1)
            hour_consistency: Percentage of drops at most common hour (0-1)
            data_age_days: Age of oldest data in days
            
        Returns:
            Confidence score (0-1)
        """
        # Base confidence from sample size
        if total_drops < 3:
            sample_confidence = 0.2
        elif total_drops < 5:
            sample_confidence = 0.4
        elif total_drops < 10:
            sample_confidence = 0.6
        elif total_drops < 20:
            sample_confidence = 0.8
        else:
            sample_confidence = 1.0
        
        # Pattern consistency confidence
        pattern_confidence = (day_consistency + hour_consistency) / 2
        
        # Data freshness confidence (decay over time)
        if data_age_days < 30:
            freshness_confidence = 1.0
        elif data_age_days < 60:
            freshness_confidence = 0.8
        elif data_age_days < 90:
            freshness_confidence = 0.6
        else:
            freshness_confidence = 0.4
        
        # Weighted average
        confidence = (
            sample_confidence * 0.4 +
            pattern_confidence * 0.4 +
            freshness_confidence * 0.2
        )
        
        return round(confidence, 2)
    
    def get_upcoming_predictions(self, hours_ahead: int = 168) -> List[Dict]:
        """
        Get all products with predicted drops in the next N hours.
        
        Args:
            hours_ahead: How many hours to look ahead (default: 168 = 1 week)
            
        Returns:
            List of predictions sorted by predicted time
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all unique products with drops
            cursor.execute("""
                SELECT DISTINCT product_url, product_name, site 
                FROM drop_history
            """)
            
            products = cursor.fetchall()
            
            predictions = []
            now = datetime.now()
            cutoff = now + timedelta(hours=hours_ahead)
            
            for product_url, product_name, site in products:
                prediction = self.predict_next_drop(product_url)
                
                if prediction['predicted_time']:
                    pred_time = datetime.fromisoformat(prediction['predicted_time'])
                    
                    if now <= pred_time <= cutoff:
                        predictions.append({
                            'product_url': product_url,
                            'product_name': product_name,
                            'site': site,
                            **prediction
                        })
            
            # Sort by predicted time
            predictions.sort(key=lambda x: x['predicted_time'])
            
            return predictions
            
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict:
        """
        Get overall prediction system statistics.
        
        Returns:
            Dictionary with system stats
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Total drops tracked
            cursor.execute("SELECT COUNT(*) FROM drop_history")
            total_drops = cursor.fetchone()[0]
            
            # Unique products
            cursor.execute("SELECT COUNT(DISTINCT product_url) FROM drop_history")
            unique_products = cursor.fetchone()[0]
            
            # Unique sites
            cursor.execute("SELECT COUNT(DISTINCT site) FROM drop_history")
            unique_sites = cursor.fetchone()[0]
            
            # Date range
            cursor.execute("""
                SELECT MIN(drop_time), MAX(drop_time) 
                FROM drop_history
            """)
            date_range = cursor.fetchone()
            
            # Most active day
            cursor.execute("""
                SELECT day_of_week, COUNT(*) as count 
                FROM drop_history 
                GROUP BY day_of_week 
                ORDER BY count DESC 
                LIMIT 1
            """)
            most_active_day = cursor.fetchone()
            
            # Most active hour
            cursor.execute("""
                SELECT hour_of_day, COUNT(*) as count 
                FROM drop_history 
                GROUP BY hour_of_day 
                ORDER BY count DESC 
                LIMIT 1
            """)
            most_active_hour = cursor.fetchone()
            
            day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            return {
                'total_drops_tracked': total_drops,
                'unique_products': unique_products,
                'unique_sites': unique_sites,
                'date_range': date_range if date_range[0] else None,
                'most_active_day': day_names[most_active_day[0]] if most_active_day else None,
                'most_active_day_count': most_active_day[1] if most_active_day else 0,
                'most_active_hour': most_active_hour[0] if most_active_hour else None,
                'most_active_hour_count': most_active_hour[1] if most_active_hour else 0
            }
            
        finally:
            conn.close()


# Convenience functions
def record_drop(
    product_url: str,
    drop_time: datetime = None,
    **kwargs
) -> int:
    """
    Convenience function to record a drop.
    
    Args:
        product_url: URL of the product
        drop_time: When the drop occurred (default: now)
        **kwargs: Additional parameters (product_name, site, price, stock_quantity)
        
    Returns:
        ID of the recorded drop
    """
    predictor = DropPredictor()
    if drop_time is None:
        drop_time = datetime.now()
    return predictor.record_drop(product_url, drop_time, **kwargs)


def predict_drop(product_url: str) -> Dict:
    """
    Convenience function to predict next drop.
    
    Args:
        product_url: URL of the product
        
    Returns:
        Prediction dictionary
    """
    predictor = DropPredictor()
    return predictor.predict_next_drop(product_url)


def analyze_product_patterns(product_url: str) -> Dict:
    """
    Convenience function to analyze product patterns.
    
    Args:
        product_url: URL of the product
        
    Returns:
        Analysis dictionary
    """
    predictor = DropPredictor()
    return predictor.analyze_product(product_url)


if __name__ == "__main__":
    # Test the predictor
    print("🔮 Drop Predictor Test")
    print("=" * 60)
    
    predictor = DropPredictor()
    
    # Record some test drops
    test_url = "https://example.com/product"
    
    print("\n📝 Recording test drops...")
    
    # Simulate drops on Fridays at 3 PM
    base_time = datetime(2025, 11, 7, 15, 0)  # Friday, Nov 7, 3 PM
    
    for week in range(4):
        drop_time = base_time + timedelta(weeks=week)
        predictor.record_drop(
            product_url=test_url,
            product_name="Test Product",
            site="example.com",
            drop_time=drop_time,
            price=99.99,
            stock_quantity=100
        )
    
    print("\n📊 Analyzing patterns...")
    analysis = predictor.analyze_product(test_url)
    
    print(f"\nTotal drops: {analysis['total_drops']}")
    print(f"Most common day: {analysis['most_common_day']} ({analysis['most_common_day_count']} times)")
    print(f"Most common hour: {analysis['most_common_hour']}:00 ({analysis['most_common_hour_count']} times)")
    print(f"Confidence score: {analysis['confidence_score']}")
    
    print("\n🔮 Predicting next drop...")
    prediction = predictor.predict_next_drop(test_url)
    
    print(f"\nPredicted time: {prediction['predicted_time']}")
    print(f"Confidence: {prediction['confidence']}")
    print(f"Pattern: {prediction['pattern_description']}")
    print(f"Rationale: {prediction['rationale']}")
    
    print("\n📈 System statistics...")
    stats = predictor.get_statistics()
    
    print(f"\nTotal drops tracked: {stats['total_drops_tracked']}")
    print(f"Unique products: {stats['unique_products']}")
    print(f"Most active day: {stats['most_active_day']} ({stats['most_active_day_count']} drops)")
    print(f"Most active hour: {stats['most_active_hour']}:00 ({stats['most_active_hour_count']} drops)")
    
    print("\n✅ Test complete!")
