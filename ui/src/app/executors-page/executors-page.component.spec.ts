import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { ExecutorsPageComponent } from './executors-page.component';

describe('ExecutorsPageComponent', () => {
  let component: ExecutorsPageComponent;
  let fixture: ComponentFixture<ExecutorsPageComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ ExecutorsPageComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(ExecutorsPageComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
