from .index_views import index
from .order_views import orders, order
from .map_views import map
from .network_views import (
    admin,
    reseau,
    create_network,
    set_network_visibility,
    set_network_validation,
    view_emails_pdf,
    view_emails,
    network_description_and_image,
    user_description_and_image,
    bestof,
)
from .delivery_views import (
    archived_deliveries,
    delete_archived_delivery,
    delete_all_archived_deliveries,
    list_delivery_models,
    create_delivery,
    set_delivery_state,
    set_delivery_name,
    active_products,
)
from .directory_views import dates_of_last_purchase, view_directory, view_history
from .message_views import editor, set_message, unset_message
from .journal_views import journal

from .getters import (
    get_network,
    get_delivery,
    get_subgroup,
    must_be_prod_or_staff,
    must_be_staff,
    must_be_subgroup_staff,
)
from .edit_delivery_purchases import edit_delivery_purchases
from .buy import buy
from .user_registration import user_register, user_update, user_deactivate
from .edit_delivery_products import edit_delivery_products, delivery_products_json
from .view_purchases import (
    view_purchases_html,
    view_purchases_latex_table,
    view_purchases_xlsx,
    view_purchases_latex_cards,
    view_purchases_json,
    all_deliveries_html,
    all_deliveries_latex,
)
from .spreadsheet import spreadsheet
from .candidacies import (
    cancel_candidacy,
    validate_candidacy,
    leave_network,
    create_candidacy,
    manage_candidacies,
)
from .invoice_mail import invoice_mail_form
from .users import users_json, users_html, user
from . import delivery_description as dd
from . import latex
