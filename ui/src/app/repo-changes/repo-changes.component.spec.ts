import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RepoChangesComponent } from './repo-changes.component';

describe('RepoChangesComponent', () => {
  let component: RepoChangesComponent;
  let fixture: ComponentFixture<RepoChangesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ RepoChangesComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(RepoChangesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
