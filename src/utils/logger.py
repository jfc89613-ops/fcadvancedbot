import logging

class CustomLogger:
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def info(self, message):
        self.logger.info(f"ℹ️ {message}")

    def warning(self, message):
        self.logger.warning(f"⚠️ {message}")

    def error(self, message):
        self.logger.error(f"❌ {message}")

    def success(self, message):
        self.logger.info(f"✅ {message}")

    def track_metric(self, metric_name, value):
        self.logger.info(f"📊 Metric '{metric_name}': {value}")

# Example usage
if __name__ == "__main__":
    logger = CustomLogger("MyLogger")
    logger.info("This is an info message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
    logger.success("This is a success message.")
    logger.track_metric("User Signups", 100)