package __PACKAGE__;

import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryPurchasesParams;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.Collections;
import java.util.List;

/**
 * Google Play subscriptions for the CyberHire web screens (Play Billing Library 8).
 * JS: Capacitor.Plugins.PlayBilling.getProduct / subscribe / getPurchases.
 * The server verifies and acknowledges every purchase token with Google before unlocking Pro.
 */
@CapacitorPlugin(name = "PlayBilling")
public class PlayBillingPlugin extends Plugin implements PurchasesUpdatedListener {
    private BillingClient client;
    private PluginCall purchaseCall;

    private interface Ready { void run(); }
    private interface ProductReady { void done(ProductDetails details); }

    @Override
    public void load() {
        client = BillingClient.newBuilder(getContext())
                .setListener(this)
                .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
                .build();
    }

    private static String code(BillingResult r) {
        return "BILLING_" + r.getResponseCode();
    }

    private void connected(PluginCall call, Ready ready) {
        if (client.isReady()) {
            ready.run();
            return;
        }
        client.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult result) {
                if (result.getResponseCode() == BillingClient.BillingResponseCode.OK) ready.run();
                else call.reject("Google Play Billing isn't available on this device: " + result.getDebugMessage(), code(result));
            }

            @Override
            public void onBillingServiceDisconnected() {
                // The next call reconnects.
            }
        });
    }

    private void queryProduct(PluginCall call, String productId, ProductReady cb) {
        QueryProductDetailsParams params = QueryProductDetailsParams.newBuilder()
                .setProductList(Collections.singletonList(QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(productId)
                        .setProductType(BillingClient.ProductType.SUBS)
                        .build()))
                .build();
        client.queryProductDetailsAsync(params, (result, details) -> {
            if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                call.reject("Couldn't load the subscription from Google Play: " + result.getDebugMessage(), code(result));
                return;
            }
            List<ProductDetails> list = details.getProductDetailsList();
            cb.done(list == null || list.isEmpty() ? null : list.get(0));
        });
    }

    /** Days of free trial in an offer (0 when it has none). Google only lists offers this user is eligible for. */
    private static int freeDays(ProductDetails.SubscriptionOfferDetails offer) {
        for (ProductDetails.PricingPhase p : offer.getPricingPhases().getPricingPhaseList()) {
            if (p.getPriceAmountMicros() == 0) return isoDays(p.getBillingPeriod()) * Math.max(1, p.getBillingCycleCount());
        }
        return 0;
    }

    private static int isoDays(String period) {
        if (period == null || period.length() < 3) return 0;
        try {
            int n = Integer.parseInt(period.substring(1, period.length() - 1));
            char unit = period.charAt(period.length() - 1);
            return unit == 'D' ? n : unit == 'W' ? n * 7 : unit == 'M' ? n * 30 : unit == 'Y' ? n * 365 : 0;
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    private static ProductDetails.SubscriptionOfferDetails pickOffer(ProductDetails d) {
        List<ProductDetails.SubscriptionOfferDetails> offers = d.getSubscriptionOfferDetails();
        if (offers == null || offers.isEmpty()) return null;
        for (ProductDetails.SubscriptionOfferDetails o : offers) if (freeDays(o) > 0) return o;
        for (ProductDetails.SubscriptionOfferDetails o : offers) if (o.getOfferId() == null) return o; // the base plan
        return offers.get(0);
    }

    private static ProductDetails.PricingPhase recurringPhase(ProductDetails.SubscriptionOfferDetails offer) {
        List<ProductDetails.PricingPhase> phases = offer.getPricingPhases().getPricingPhaseList();
        for (ProductDetails.PricingPhase p : phases) {
            if (p.getRecurrenceMode() == ProductDetails.RecurrenceMode.INFINITE_RECURRING) return p;
        }
        return phases.get(phases.size() - 1);
    }

    private static JSObject toJs(Purchase p) {
        JSObject o = new JSObject();
        o.put("purchaseToken", p.getPurchaseToken());
        o.put("productId", p.getProducts().isEmpty() ? "" : p.getProducts().get(0));
        o.put("acknowledged", p.isAcknowledged());
        return o;
    }

    @PluginMethod
    public void getProduct(PluginCall call) {
        String id = call.getString("productId", "cyberhire_pro");
        connected(call, () -> queryProduct(call, id, details -> {
            JSObject ret = new JSObject();
            ret.put("productId", id);
            if (details == null) {
                ret.put("available", false);
                call.resolve(ret);
                return;
            }
            ProductDetails.SubscriptionOfferDetails offer = pickOffer(details);
            ret.put("available", offer != null);
            ret.put("title", details.getName());
            if (offer != null) {
                ProductDetails.PricingPhase phase = recurringPhase(offer);
                ret.put("price", phase.getFormattedPrice());
                ret.put("billingPeriod", phase.getBillingPeriod());
                ret.put("trialDays", freeDays(offer));
            }
            call.resolve(ret);
        }));
    }

    @PluginMethod
    public void subscribe(PluginCall call) {
        String id = call.getString("productId", "cyberhire_pro");
        String accountId = call.getString("accountId");
        if (purchaseCall != null) {
            call.reject("A purchase is already in progress.", "BUSY");
            return;
        }
        connected(call, () -> queryProduct(call, id, details -> {
            ProductDetails.SubscriptionOfferDetails offer = details == null ? null : pickOffer(details);
            if (offer == null) {
                call.reject("This subscription isn't available right now.", "PRODUCT_NOT_FOUND");
                return;
            }
            BillingFlowParams.ProductDetailsParams item = BillingFlowParams.ProductDetailsParams.newBuilder()
                    .setProductDetails(details)
                    .setOfferToken(offer.getOfferToken())
                    .build();
            BillingFlowParams.Builder flow = BillingFlowParams.newBuilder().setProductDetailsParamsList(Collections.singletonList(item));
            if (accountId != null && !accountId.isEmpty()) flow.setObfuscatedAccountId(accountId);
            purchaseCall = call;
            getActivity().runOnUiThread(() -> {
                BillingResult r = client.launchBillingFlow(getActivity(), flow.build());
                if (r.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                    purchaseCall = null;
                    call.reject("Google Play couldn't start the purchase: " + r.getDebugMessage(), code(r));
                }
            });
        }));
    }

    @Override
    public void onPurchasesUpdated(BillingResult result, List<Purchase> purchases) {
        PluginCall call = purchaseCall;
        purchaseCall = null;
        if (call == null) return;
        int rc = result.getResponseCode();
        if (rc == BillingClient.BillingResponseCode.OK && purchases != null && !purchases.isEmpty()) {
            Purchase p = purchases.get(0);
            if (p.getPurchaseState() == Purchase.PurchaseState.PENDING) {
                call.reject("Your payment is pending. Pro unlocks as soon as Google Play confirms it; then tap Restore purchase.", "PENDING");
                return;
            }
            call.resolve(toJs(p));
        } else if (rc == BillingClient.BillingResponseCode.USER_CANCELED) {
            call.reject("Purchase cancelled", "USER_CANCELED");
        } else if (rc == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
            call.reject("You already have this subscription. Tap Restore purchase.", "ALREADY_OWNED");
        } else {
            call.reject("Google Play couldn't complete the purchase (" + result.getDebugMessage() + ")", code(result));
        }
    }

    @PluginMethod
    public void getPurchases(PluginCall call) {
        connected(call, () -> client.queryPurchasesAsync(
                QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build(),
                (result, list) -> {
                    if (result.getResponseCode() != BillingClient.BillingResponseCode.OK) {
                        call.reject("Couldn't check your Google Play purchases: " + result.getDebugMessage(), code(result));
                        return;
                    }
                    JSArray arr = new JSArray();
                    for (Purchase p : list) {
                        if (p.getPurchaseState() == Purchase.PurchaseState.PURCHASED) arr.put(toJs(p));
                    }
                    JSObject ret = new JSObject();
                    ret.put("purchases", arr);
                    call.resolve(ret);
                }));
    }
}
