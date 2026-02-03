from rental_manager.domain import models


def main() -> None:
    product = models.Product(
        id=None,
        name="Mesa",
        category="mesa",
        total_qty=10,
        unit_price=25.0,
        active=True,
    )
    print(product)


if __name__ == "__main__":
    main()
