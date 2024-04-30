%define app_path /www/ood/apps/sys/
%define widgets_path /etc/ood/config/apps/dashboard/widgets/

Name:           ood-cloud-storage-conf
Version:        1
Release:        1%{?dist}
Summary:        Open on Demand Cloud Storage Configuration API

BuildArch:      %{_arch}

License:        MIT
Source:         %{name}-%{version}.tar.bz2

Requires:       ondemand
Requires:       ood-lumi-o-tools
Obsoletes:      ood-allas-auth

# Disable debuginfo
%global debug_package %{nil}

%description
Open on Demand Cloud Storage Configuration API

%prep
%setup -q

%build

%install


%__mkdir_p  %{buildroot}%{_sharedstatedir}/ondemand-nginx/config/apps/sys
touch       %{buildroot}%{_sharedstatedir}/ondemand-nginx/config/apps/sys/ood-cloud-storage-conf.conf

%__install -m 0755 -d %{buildroot}%{_localstatedir}%{app_path}%{name}/{allas_auth,bin,dist}
%__install -m 0755 -d %{buildroot}%{opt_path}
%__install -m 0755 -d %{buildroot}%{widgets_path}
%__install -m 0755 bin/python %{buildroot}%{_localstatedir}%{app_path}%{name}/bin
%__install -m 0644 app.py passenger_wsgi.py LICENSE manifest.yml %{buildroot}%{_localstatedir}%{app_path}%{name}/
%__install -m 0644 -D allas_auth/*.py %{buildroot}%{_localstatedir}%{app_path}%{name}/allas_auth/
%__install -m 0644 widgets/_cloud_storage.html.erb %{buildroot}%{widgets_path}

./ood_install.sh

for file in $(find deps/{lib,lib64,share} -type f); do
  %__install -m 0644 -D ${file} %{buildroot}%{_localstatedir}%{app_path}%{name}/${file}
done

for file in $(find deps/bin -type f); do
  %__install -m 0755 -D ${file} %{buildroot}%{_localstatedir}%{app_path}%{name}/${file}
done

%post

touch %{_sharedstatedir}/ondemand-nginx/config/apps/sys/ood-cloud-storage-conf.conf

%files

%{_localstatedir}%{app_path}%{name}
%{widgets_path}_cloud_storage.html.erb
%ghost %{_sharedstatedir}/ondemand-nginx/config/apps/sys/ood-cloud-storage-conf.conf

%changelog
* Tue Aug 22 2023 Robin Karlsson <robin.karlsson@csc.fi>
- Initial version
