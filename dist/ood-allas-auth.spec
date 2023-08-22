%define app_path /www/ood/apps/sys/

Name:           ood-allas-auth
Version:        1
Release:        1%{?dist}
Summary:        Open on Demand Allas auth API

BuildArch:      %{_arch}

License:        MIT
Source:         %{name}-%{version}.tar.bz2

Requires:       ondemand

# Disable debuginfo
%global debug_package %{nil}

%description
Open on Demand Allas auth API

%prep
%setup -q

%build

%install


%__mkdir_p  %{buildroot}%{_sharedstatedir}/ondemand-nginx/config/apps/sys
touch       %{buildroot}%{_sharedstatedir}/ondemand-nginx/config/apps/sys/ood-allas-auth.conf

%__install -m 0755 -d %{buildroot}%{_localstatedir}%{app_path}%{name}/{bin,dist,templates}
%__install -m 0755 bin/{allas-conf,env,python} %{buildroot}%{_localstatedir}%{app_path}%{name}/bin
%__install -m 0644 app.py passenger_wsgi.py LICENSE manifest.yml %{buildroot}%{_localstatedir}%{app_path}%{name}/

./ood_install.sh

for file in $(find deps/{lib,lib64,share} -type f); do
  %__install -m 0644 -D ${file} %{buildroot}%{_localstatedir}%{app_path}%{name}/${file}
done

for file in $(find deps/bin -type f); do
  %__install -m 0755 -D ${file} %{buildroot}%{_localstatedir}%{app_path}%{name}/${file}
done

%post

%files

%{_localstatedir}%{app_path}%{name}
%{_sharedstatedir}/ondemand-nginx/config/apps/sys/ood-allas-auth.conf

%changelog
* Tue Aug 22 2023 Robin Karlsson <robin.karlsson@csc.fi>
- Initial version
