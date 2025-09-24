# def selection_sort(arr):
#     n = len(arr)
#     for i in range(n):
#         min_index = i
#         for j in range(i+1, n):
#             if arr[j] < arr[min_index]:
#                 min_index = j
#         arr[i], arr[min_index] = arr[min_index], arr[i]
#     return arr
# import math
# def selection_sort(arr):
#     try:
#         if not isinstance(arr, list):  # Periksa apakah input adalah list
#             raise TypeError("Input must be a list")
        
#         for element in arr:  # Validasi elemen dalam array
#             if not isinstance(element, (int, float)):
#                 raise TypeError(f"elemen: {element} dalam array harus int atau float yang valid")
#             if isinstance(element, float) and (element != element):  # Periksa NaN
#                 raise ValueError("Array berisi nilai NaN")

#         # Algoritma Selection Sort
#         n = len(arr)
#         for i in range(n):
#             min_index = i
#             for j in range(i + 1, n):
#                 if arr[j] < arr[min_index]:
#                     min_index = j
#             arr[i], arr[min_index] = arr[min_index], arr[i]
#         return arr

#     except (TypeError, ValueError) as e:
#         print(f"Error: {e}")  # Menampilkan pesan error
#         raise

import math

def selection_sort(arr):
    # Validasi input adalah list
    if not isinstance(arr, list):
        raise TypeError("Input harus berupa list array")

    # Pisahkan elemen angka dan string
    numbers = []
    strings = []
    for element in arr:
        if isinstance(element, (int, float)):
            if isinstance(element, float) and math.isnan(element):  # Periksa NaN
                numbers.append(float('inf'))  # Perlakukan NaN sebagai nilai terbesar
            else:
                numbers.append(element)
        elif isinstance(element, str):
            strings.append(element)
        else:
            raise TypeError(f"Elemen: {element} tidak valid, harus int, float, atau string")

    # Sorting elemen angka dengan selection sort
    n = len(numbers)
    for i in range(n):
        min_index = i
        for j in range(i + 1, n):
            if numbers[j] < numbers[min_index]:
                min_index = j
        numbers[i], numbers[min_index] = numbers[min_index], numbers[i]

    # Sorting elemen string secara leksikografis
    strings.sort()

    # Gabungkan angka dan string (angka di depan)
    return numbers + strings


def quick_sort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[0]
    left = [x for x in arr[1:] if x < pivot]
    right = [x for x in arr[1:] if x >= pivot]
    return quick_sort(left) + [pivot] + quick_sort(right)

# Data yang akan diurutkan
data = ["dua", "", 1, -2, 9.0, math.nan]

# Panggil fungsi
sorted_data = selection_sort(data)

# Tampilkan hasilnya
print("Hasil pengurutan:", sorted_data)
