import { toast } from "sonner";
import { BRAND } from "./brandConfig";

export const LOCKED_FEATURES = {
  virtualCustomer: true,
  salesDashboard: true,
  marketingDashboard: true,
  notifications: true,
};

export const LOCKED_PATHS = {
  "/virtual-customer": "virtualCustomer",
  "/sales-dashboard": "salesDashboard",
  "/marketing-dashboard": "marketingDashboard",
  "/notifications": "notifications",
};

export const SHOW_PROJECT_DISTRIBUTION = false;

export const isVcPreviewMode = () => LOCKED_FEATURES.virtualCustomer === "preview";

export const isVcFullyLocked = () => LOCKED_FEATURES.virtualCustomer === true;

export const isFeatureLocked = (key) => {
  if (key === "virtualCustomer" && isVcPreviewMode()) {
    return false;
  }
  return LOCKED_FEATURES[key] === true;
};

export const isPathLocked = (path) => {
  if (path === "/virtual-customer" && isVcPreviewMode()) {
    return false;
  }
  const key = LOCKED_PATHS[path];
  return key ? isFeatureLocked(key) : false;
};

export const isPathPreview = (path) =>
  path === "/virtual-customer" && isVcPreviewMode();

export const isVirtualCustomerLocked = () => isFeatureLocked("virtualCustomer");

export function getVirtualCustomerHomePath(isAdmin = false) {
  if (isVirtualCustomerLocked()) {
    return isAdmin ? "/dashboard" : "/my-dashboard";
  }
  return "/virtual-customer";
}

function showVirtualCustomerLockedToast() {
  toast.info("Virtual Customer is locked", {
    description: BRAND.supportMessage,
  });
}

/** Navigate to Virtual Customer list/search — blocked when feature is locked. */
export function navigateToVirtualCustomer(navigate, path = "/virtual-customer") {
  if (isVirtualCustomerLocked()) {
    showVirtualCustomerLockedToast();
    return false;
  }
  navigate(path);
  return true;
}

/** Navigate to a lead profile — same lock as Virtual Customer. */
export function navigateToCustomerDetail(navigate, leadId) {
  if (!leadId) return false;
  if (isVirtualCustomerLocked()) {
    showVirtualCustomerLockedToast();
    return false;
  }
  navigate(`/customer/${leadId}`);
  return true;
}
