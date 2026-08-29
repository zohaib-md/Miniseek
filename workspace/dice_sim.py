import random
import statistics

# Simulate rolling two 6-sided dice 500 times
results = [random.randint(1, 6) + random.randint(1, 6) for _ in range(500)]

# Calculate the frequency of each sum from 2 to 12
sum_counts = {sum_val: results.count(sum_val) for sum_val in range(2, 13)}

# Print the frequency of each sum
for sum_val, count in sum_counts.items():
    print(f'Sum {sum_val} occurred {count} times')
