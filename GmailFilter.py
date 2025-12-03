from EmailLoader import Data
from Filters import Filter

if __name__ == "__main__":
    data = Data()
    filter_instance = Filter()
    filter_instance.filter_messages(data)
